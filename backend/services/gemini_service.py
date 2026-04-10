import google.generativeai as genai
import os
import json
import re
import logging
import asyncio
import itertools

logger = logging.getLogger(__name__)

# 3-Key rotation system for quota distribution
API_KEYS = [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
]

# Validate that all keys are present
if not all(API_KEYS):
    logger.error("❌ Missing API keys! Set GEMINI_API_KEY_1, GEMINI_API_KEY_2, GEMINI_API_KEY_3 in .env")
    raise RuntimeError("Not all Gemini API keys configured in .env")

_key_cycle = itertools.cycle(API_KEYS)

# Valid Gemini model name
GEMINI_MODEL = "gemini-2.5-flash"

LANGUAGE_MAP = {
    "hi": "Hindi",
    "te": "Telugu",
    "ta": "Tamil",
    "en": "English",
}


def get_model():
    """Get a fresh Gemini model instance with key rotation"""
    key = next(_key_cycle)

    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel(GEMINI_MODEL)
        logger.debug(f"✓ Configured with rotated key, model: {GEMINI_MODEL}")
        return model
    except Exception as e:
        logger.error(f"Failed to initialize model: {str(e)[:100]}")
        raise


async def call_with_retry(fn):
    """Retry wrapper for quota handling - automatically rotates to next API key if quota hit"""

    for attempt in range(len(API_KEYS)):
        try:
            return await fn()
        except Exception as e:
            err = str(e)
            is_quota_error = ("429" in err or "quota" in err.lower() or
                            "exhausted" in err.lower() or "rate limit" in err.lower())

            if is_quota_error and attempt < len(API_KEYS) - 1:
                logger.warning(f"⚠️ Quota hit on current key (attempt {attempt + 1}/{len(API_KEYS)}), rotating to next key...")
                await asyncio.sleep(0.5)  # Non-blocking delay before retry
                continue
            # Not a quota error or all keys exhausted, propagate it
            raise e

    raise Exception("❌ All API keys have hit quota. Try again after midnight GMT or add more keys.")


def parse_json(text: str) -> dict:
    """Robust JSON parser that handles markdown code blocks"""
    try:
        text = text.strip()
        # Remove markdown code blocks if present
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        # Extract first JSON object
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"No valid JSON found in response: {text[:300]}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        raise ValueError(f"Invalid JSON in response: {str(e)}")


async def analyze_crop_image(image_b64: str, mime_type: str) -> dict:
    """Analyze crop/leaf image for diseases using Gemini Vision"""
    async def _analyze():
        prompt = """
        You are an expert agronomist. Analyze this crop/plant image and provide:
        1. Crop name (what plant/crop is this — be specific e.g. Tomato, Wheat, Rice, Cotton, Potato)
        2. Disease name (if any, or "Healthy" if no disease)
        3. Confidence level (High/Medium/Low)
        4. Symptoms observed
        5. Cause (fungal/bacterial/viral/pest/nutrient deficiency)
        6. Treatment steps (specific, actionable)
        7. Preventive measures
        8. Recommended pesticides/fungicides (common Indian brands)
        9. Urgency level (Immediate/Within a week/Monitor)

        Respond ONLY in this exact JSON format:
        {
          "crop_name": "string (e.g. Tomato, Wheat, Rice, Cotton, Potato)",
          "disease": "string",
          "is_healthy": boolean,
          "confidence": "High|Medium|Low",
          "symptoms": ["list"],
          "cause": "string",
          "treatment": ["step 1", "step 2"],
          "prevention": ["tip 1", "tip 2"],
          "products": ["product name"],
          "urgency": "Immediate|Within a week|Monitor"
        }
        """
        image_part = {
            "inline_data": {"mime_type": mime_type, "data": image_b64}
        }
        model = get_model()  # Fresh model with rotated key for each call
        response = model.generate_content([prompt, image_part])
        return parse_json(response.text)

    try:
        return await call_with_retry(_analyze)
    except Exception as e:
        logger.error(f"Error analyzing crop image: {e}")
        raise ValueError(f"Failed to analyze crop image: {str(e)}")


async def analyze_soil(soil_data: dict) -> dict:
    """Analyze soil parameters and give recommendations"""
    async def _analyze():
        prompt = f"""
        You are an expert soil scientist. Analyze this soil data for a farmer in {soil_data['location']}, India:
        - Nitrogen (N): {soil_data['nitrogen']} kg/ha
        - Phosphorus (P): {soil_data['phosphorus']} kg/ha
        - Potassium (K): {soil_data['potassium']} kg/ha
        - pH: {soil_data['ph']}
        - Moisture: {soil_data['moisture']}%
        - Desired Crop: {soil_data['crop_type']}

        Provide recommendations in this JSON format:
        {{
          "soil_health": "Poor|Fair|Good|Excellent",
          "ph_status": "Acidic|Neutral|Alkaline",
          "deficiencies": ["list of nutrients that are low"],
          "fertilizer_recommendation": [
            {{"name": "fertilizer name", "quantity": "amount per acre", "timing": "when to apply"}}
          ],
          "best_crops": ["crop1", "crop2", "crop3"],
          "crop_suitability": "High|Medium|Low for {soil_data['crop_type']}",
          "improvement_tips": ["tip1", "tip2"],
          "estimated_yield": "string"
        }}
        """
        model = get_model()  # Fresh model with rotated key for each call
        response = model.generate_content(prompt)
        return parse_json(response.text)

    try:
        return await call_with_retry(_analyze)
    except Exception as e:
        logger.error(f"Error analyzing soil: {e}")
        raise ValueError(f"Failed to analyze soil: {str(e)}")


async def chat_with_farmer(message: str, language: str, history: list) -> str:
    """Multilingual farming assistant chatbot"""
    async def _chat():
        lang_name = LANGUAGE_MAP.get(language, "English")

        system_prompt = f"""You are KisanAI, a friendly and knowledgeable farming assistant for Indian farmers.
Always respond in {lang_name}.
You help with: crop diseases, fertilizers, irrigation, weather, government schemes, market prices.
Keep responses concise, practical, and easy to understand for rural farmers.
Use simple language, avoid technical jargon unless necessary."""

        # Convert chat history from OpenAI format (user/assistant) to Gemini format (user/model)
        chat_history = []
        for msg in history[-6:]:  # last 6 messages for context
            # Map OpenAI role names to Gemini role names
            role = msg.get("role", "user")
            if role == "assistant":
                role = "model"
            elif role != "user":
                role = "user"

            content = msg.get("content", "")
            # Gemini expects parts to be a list of objects with 'text' key
            chat_history.append({"role": role, "parts": [{"text": content}]})

        model = get_model()  # Fresh model with rotated key for each call
        chat = model.start_chat(history=chat_history)
        response = chat.send_message(f"{system_prompt}\n\nFarmer's question: {message}")
        return response.text

    try:
        return await call_with_retry(_chat)
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        raise ValueError(f"Failed to process chat: {str(e)}")
