"""
Multi-Language Translator
Automatic translation from Greek/English to French using deep-translator
"""

import logging
from typing import Dict, List, Optional
import time

from deep_translator import GoogleTranslator, MyMemoryTranslator
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException


# Set seed for consistent language detection
DetectorFactory.seed = 0


class Translator:
    """
    Handles automatic translation of event data
    """

    def __init__(self, config: Dict):
        """
        Initialize Translator

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.translation_config = config.get('translation', {})

        # Initialize translators
        self.target_lang = self.translation_config.get('target_language', 'fr')
        self.source_langs = self.translation_config.get('source_languages', ['el', 'en'])

        # Primary translator
        self.translator = GoogleTranslator(target=self.target_lang)

        # Fallback translator
        self.fallback_translator = MyMemoryTranslator(target=self.target_lang)

        # Fields to translate
        self.fields_to_translate = self.translation_config.get('fields_to_translate', [
            'title', 'subtitle', 'description', 'excerpt',
            'venue_name', 'venue_address', 'venue_city',
            'organizer_name', 'category', 'tags'
        ])

        # Cache for translations
        self.translation_cache = {}

        self.logger.info(f"Translator initialized (target: {self.target_lang})")

    def detect_language(self, text: str) -> Optional[str]:
        """
        Detect the language of text

        Args:
            text: Text to analyze

        Returns:
            ISO 639-1 language code or None
        """
        if not text or len(text.strip()) < 3:
            return None

        try:
            lang = detect(text)
            self.logger.debug(f"Detected language: {lang} for text: {text[:50]}...")
            return lang
        except LangDetectException as e:
            self.logger.debug(f"Language detection failed: {e}")
            return None

    def should_translate(self, text: str, detected_lang: Optional[str] = None) -> bool:
        """
        Determine if text should be translated

        Args:
            text: Text to check
            detected_lang: Pre-detected language (optional)

        Returns:
            True if translation needed, False otherwise
        """
        if not text or not self.translation_config.get('enabled', True):
            return False

        # Skip if already in target language
        if detected_lang is None:
            detected_lang = self.detect_language(text)

        if detected_lang is None:
            return False

        # Only translate if from source languages
        return detected_lang in self.source_langs

    def translate_text(
        self,
        text: str,
        source_lang: Optional[str] = None,
        use_cache: bool = True
    ) -> Optional[str]:
        """
        Translate a single text string

        Args:
            text: Text to translate
            source_lang: Source language (auto-detect if None)
            use_cache: Use translation cache

        Returns:
            Translated text or None if translation fails
        """
        if not text or not isinstance(text, str):
            return None

        # Clean text
        text = text.strip()

        if len(text) < 2:
            return text

        # Check cache
        if use_cache and text in self.translation_cache:
            self.logger.debug(f"Using cached translation for: {text[:30]}...")
            return self.translation_cache[text]

        # Auto-detect language if needed
        if source_lang is None and self.translation_config.get('auto_detect_language', True):
            detected_lang = self.detect_language(text)
            if not self.should_translate(text, detected_lang):
                self.logger.debug(f"Skipping translation (lang: {detected_lang})")
                return text
            source_lang = detected_lang

        try:
            # Translate
            self.logger.debug(f"Translating ({source_lang} -> {self.target_lang}): {text[:50]}...")

            # Update translator source language
            if source_lang and source_lang != 'auto':
                self.translator = GoogleTranslator(source=source_lang, target=self.target_lang)

            translated = self.translator.translate(text)

            # Cache translation
            if use_cache and translated:
                self.translation_cache[text] = translated

            # Small delay to avoid rate limiting
            time.sleep(0.1)

            return translated

        except Exception as e:
            self.logger.warning(f"Primary translation failed: {e}")

            # Try fallback translator
            try:
                self.logger.debug("Trying fallback translator...")
                if source_lang and source_lang != 'auto':
                    self.fallback_translator = MyMemoryTranslator(
                        source=source_lang,
                        target=self.target_lang
                    )

                translated = self.fallback_translator.translate(text)

                if use_cache and translated:
                    self.translation_cache[text] = translated

                time.sleep(0.2)

                return translated

            except Exception as e2:
                self.logger.error(f"Fallback translation failed: {e2}")
                return None

    def translate_event(self, event: Dict) -> Dict:
        """
        Translate all translatable fields in an event

        Args:
            event: Event dictionary

        Returns:
            Event with translated fields added (original + _fr versions)
        """
        if not self.translation_config.get('enabled', True):
            return event

        translated_event = event.copy()

        # Detect primary language from title
        title = event.get('title', '')
        detected_lang = self.detect_language(title) if title else None

        # Translate each field
        for field in self.fields_to_translate:
            original_value = event.get(field)

            if not original_value:
                continue

            # Handle different value types
            if isinstance(original_value, str):
                translated_value = self.translate_text(
                    original_value,
                    source_lang=detected_lang
                )

                if translated_value and translated_value != original_value:
                    # Add translated field
                    translated_field_name = f"{field}_fr"
                    translated_event[translated_field_name] = translated_value
                    self.logger.debug(f"Translated {field}: {original_value[:30]} -> {translated_value[:30]}")
                else:
                    # No translation or same as original
                    translated_event[f"{field}_fr"] = original_value

            elif isinstance(original_value, list):
                # Handle lists (e.g., tags)
                translated_list = []
                for item in original_value:
                    if isinstance(item, str):
                        translated_item = self.translate_text(item, source_lang=detected_lang)
                        translated_list.append(translated_item if translated_item else item)
                    else:
                        translated_list.append(item)

                translated_event[f"{field}_fr"] = translated_list

        return translated_event

    def translate_batch(self, events: List[Dict]) -> List[Dict]:
        """
        Translate multiple events

        Args:
            events: List of event dictionaries

        Returns:
            List of events with translations
        """
        translated_events = []

        batch_size = self.translation_config.get('batch_size', 10)

        for i, event in enumerate(events):
            try:
                self.logger.info(f"Translating event {i+1}/{len(events)}: {event.get('title', 'Unknown')[:50]}")
                translated_event = self.translate_event(event)
                translated_events.append(translated_event)

                # Pause between batches to avoid rate limiting
                if (i + 1) % batch_size == 0:
                    self.logger.debug(f"Processed batch of {batch_size}, pausing...")
                    time.sleep(1)

            except Exception as e:
                self.logger.error(f"Failed to translate event: {e}")
                # Add original event even if translation fails
                translated_events.append(event)

        self.logger.info(f"Translation complete: {len(translated_events)} events processed")

        return translated_events

    def get_translation_stats(self) -> Dict:
        """
        Get translation statistics

        Returns:
            Dictionary with translation stats
        """
        return {
            'cache_size': len(self.translation_cache),
            'target_language': self.target_lang,
            'source_languages': self.source_langs,
            'fields_translated': self.fields_to_translate
        }

    def clear_cache(self):
        """
        Clear translation cache
        """
        self.translation_cache.clear()
        self.logger.info("Translation cache cleared")

    def set_target_language(self, lang_code: str):
        """
        Change target language

        Args:
            lang_code: ISO 639-1 language code
        """
        self.target_lang = lang_code
        self.translator = GoogleTranslator(target=lang_code)
        self.fallback_translator = MyMemoryTranslator(target=lang_code)
        self.logger.info(f"Target language changed to: {lang_code}")

    def translate_list_to_string(self, items: List[str], separator: str = ", ") -> str:
        """
        Translate a list and convert to string

        Args:
            items: List of strings
            separator: Separator for joining

        Returns:
            Translated and joined string
        """
        if not items:
            return ""

        translated_items = []
        for item in items:
            translated = self.translate_text(item)
            if translated:
                translated_items.append(translated)

        return separator.join(translated_items)

    def batch_translate_field(
        self,
        texts: List[str],
        source_lang: Optional[str] = None
    ) -> List[str]:
        """
        Translate a batch of similar texts efficiently

        Args:
            texts: List of texts to translate
            source_lang: Source language

        Returns:
            List of translated texts
        """
        translated = []

        for text in texts:
            if text:
                result = self.translate_text(text, source_lang=source_lang)
                translated.append(result if result else text)
            else:
                translated.append(text)

        return translated
