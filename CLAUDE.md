# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Code Style

- Do not add comments to code when editing. The codebase intentionally has minimal comments.

## Project Overview

youtube-search-next is a Python library for searching YouTube videos, channels, and playlists without using the YouTube Data API v3. It's a fork of youtube-search-python.

## Build and Install

```bash
pip install -e .
```

## Running Tests

Tests are located in `tests/sync/` and `tests/async/`. Run them directly with Python:

```bash
# Run sync tests
python tests/sync/search.py
python tests/sync/playlists.py
python tests/sync/extras.py

# Run async tests
python tests/async/search.py
python tests/async/playlists.py
python tests/async/extras.py
```

## Architecture

### Sync vs Async API

The library provides two APIs with identical functionality:
- **Sync**: Import from `youtubesearchpython` - calls block until complete
- **Async**: Import from `youtubesearchpython.__future__` - uses `await` for all operations

### Core Structure

**`youtubesearchpython/core/`** - Core implementations:
- `search.py` - `SearchCore` base class for all search operations
- `requests.py` - `RequestCore` handles HTTP via httpx (sync and async)
- `constants.py` - YouTube API endpoints, payload templates, filter constants
- `video.py`, `playlist.py`, `channel.py`, `transcript.py`, `comments.py` - Entity-specific logic

**`youtubesearchpython/handlers/`** - Response parsing:
- `componenthandler.py` - Extracts video/channel/playlist data from YouTube responses
- `requesthandler.py` - Request building and response parsing

**`youtubesearchpython/`** - Public sync API:
- `search.py` - `Search`, `VideosSearch`, `ChannelsSearch`, `PlaylistsSearch`, `CustomSearch`, `ChannelSearch`
- `extras.py` - `Video`, `Playlist`, `Suggestions`, `Hashtag`, `Comments`, `Transcript`, `Channel`
- `streamurlfetcher.py` - `StreamURLFetcher` for getting playable stream URLs

**`youtubesearchpython/__future__/`** - Public async API (mirrors sync API)

### Inheritance Pattern

Search classes follow this hierarchy:
```
SearchCore (core/search.py)
  └── inherits from RequestCore, RequestHandler, ComponentHandler
        └── Search, VideosSearch, ChannelsSearch, etc. (search.py)
```

### Key Constants

`core/constants.py` contains:
- `requestPayload` - Base YouTube API request body
- `searchKey` - YouTube internal API key
- `ResultMode` - Output format (dict or json)
- `SearchMode`, `VideoUploadDateFilter`, `VideoDurationFilter`, `VideoSortOrder` - Search filters

### HTTP Layer

All HTTP requests go through `core/requests.py`:
- Uses httpx for both sync and async
- Supports proxy via `HTTPS_PROXY` or `HTTP_PROXY` environment variables
- Sets appropriate User-Agent and consent cookies
