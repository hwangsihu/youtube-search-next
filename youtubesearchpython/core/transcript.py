import xml.etree.ElementTree as ET
from typing import Union, List
from urllib.parse import urlencode

from youtubesearchpython.core.constants import *
from youtubesearchpython.core.requests import RequestCore
from youtubesearchpython.core.componenthandler import getValue, getVideoId


class TranscriptCore(RequestCore):
    def __init__(self, videoLink: str, key: str):
        super().__init__()
        self.videoLink = videoLink
        self.key = key  # Now used as language code for translation
        self.captionTracks = []
        self.translationLanguages = []

    def prepare_player_request(self):
        """Prepare request to player API to get caption tracks."""
        self.url = 'https://www.youtube.com/youtubei/v1/player'
        self.data = {
            'context': {
                'client': {
                    'hl': 'en',
                    'gl': 'US',
                    'clientName': 'ANDROID',
                    'clientVersion': '19.09.37',
                    'androidSdkVersion': 30,
                }
            },
            'videoId': getVideoId(self.videoLink)
        }

    def extract_caption_tracks(self, response):
        """Extract caption tracks and translation languages from player response."""
        j = response.json()
        captions = getValue(j, ["captions"])
        if not captions:
            self.result = {"segments": [], "languages": []}
            return True

        renderer = getValue(captions, ["playerCaptionsTracklistRenderer"])
        if not renderer:
            self.result = {"segments": [], "languages": []}
            return True

        self.captionTracks = getValue(renderer, ["captionTracks"]) or []
        self.translationLanguages = getValue(renderer, ["translationLanguages"]) or []

        if not self.captionTracks:
            self.result = {"segments": [], "languages": []}
            return True

        return False

    def get_transcript_url(self):
        """Get the transcript URL, optionally with translation."""
        if not self.captionTracks:
            return None

        base_url = self.captionTracks[0].get('baseUrl', '')

        # If key (language code) is provided, add translation parameter
        if self.key:
            base_url += '&tlang=' + self.key

        return base_url

    def parse_transcript_xml(self, xml_content):
        """Parse timedtext XML to extract segments."""
        segments = []
        try:
            root = ET.fromstring(xml_content)
            for p in root.findall('.//p'):
                t = int(p.get('t', 0))
                d = int(p.get('d', 0))
                # Get text (handle nested <s> tags)
                text = ''.join(p.itertext())
                if text.strip():
                    # Convert ms to time string
                    start_sec = t // 1000
                    start_time = f"{start_sec // 60}:{start_sec % 60:02d}"
                    segments.append({
                        "startMs": str(t),
                        "endMs": str(t + d),
                        "text": text.strip(),
                        "startTime": start_time
                    })
        except ET.ParseError:
            pass
        return segments

    def build_languages_list(self):
        """Build list of available languages."""
        languages = []

        # Add original caption tracks
        for track in self.captionTracks:
            lang_code = track.get('languageCode', '')
            lang_name = getValue(track, ['name', 'simpleText']) or lang_code
            languages.append({
                "params": lang_code,
                "selected": not self.key or self.key == lang_code,
                "title": lang_name
            })

        # Add translation languages
        for lang in self.translationLanguages:
            lang_code = lang.get('languageCode', '')
            lang_name = getValue(lang, ['languageName', 'simpleText']) or lang_code
            # Skip if already in caption tracks
            if not any(t.get('languageCode') == lang_code for t in self.captionTracks):
                languages.append({
                    "params": lang_code,
                    "selected": self.key == lang_code,
                    "title": lang_name + " (auto-translated)"
                })

        return languages

    def sync_fetch_transcript(self):
        """Synchronously fetch transcript from URL."""
        transcript_url = self.get_transcript_url()
        if not transcript_url:
            self.result = {"segments": [], "languages": []}
            return

        # Use httpx directly for GET request
        import httpx
        response = httpx.get(transcript_url, timeout=self.timeout if hasattr(self, 'timeout') and self.timeout else 30)

        if response.status_code == 200:
            segments = self.parse_transcript_xml(response.text)
            languages = self.build_languages_list()
            self.result = {
                "segments": segments,
                "languages": languages
            }
        else:
            self.result = {"segments": [], "languages": []}

    async def async_fetch_transcript(self):
        """Asynchronously fetch transcript from URL."""
        transcript_url = self.get_transcript_url()
        if not transcript_url:
            self.result = {"segments": [], "languages": []}
            return

        # Use httpx directly for GET request
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(transcript_url, timeout=self.timeout if hasattr(self, 'timeout') and self.timeout else 30)

        if response.status_code == 200:
            segments = self.parse_transcript_xml(response.text)
            languages = self.build_languages_list()
            self.result = {
                "segments": segments,
                "languages": languages
            }
        else:
            self.result = {"segments": [], "languages": []}

    def sync_create(self):
        """Synchronous entry point."""
        self.prepare_player_request()
        response = self.syncPostRequest()
        if self.extract_caption_tracks(response):
            return
        self.sync_fetch_transcript()

    async def async_create(self):
        """Asynchronous entry point."""
        self.prepare_player_request()
        response = await self.asyncPostRequest()
        if self.extract_caption_tracks(response):
            return
        await self.async_fetch_transcript()
