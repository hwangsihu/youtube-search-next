import collections
import copy
import itertools
import json
from typing import Iterable, Mapping, Tuple, TypeVar, Union, List
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from youtubesearchpython.core.componenthandler import getVideoId, getValue
from youtubesearchpython.core.constants import *
from youtubesearchpython.core.requests import RequestCore

K = TypeVar("K")
T = TypeVar("T")


class CommentsCore(RequestCore):
    result = None
    continuationKey = None
    isNextRequest = False
    response = None

    def __init__(self, videoLink: str):
        super().__init__()
        self.commentsComponent = {"result": []}
        self.responseSource = None
        self.fullResponse = None
        self.videoLink = videoLink

    def prepare_continuation_request(self):
        self.data = {
            "context": {"client": {"clientName": "WEB", "clientVersion": "2.20260114.08.00"}},
            "videoId": getVideoId(self.videoLink)
        }
        self.url = f"https://www.youtube.com/youtubei/v1/next?key={searchKey}"

    def prepare_comments_request(self):
        self.data = {
            "context": {"client": {"clientName": "WEB", "clientVersion": "2.20260114.08.00"}},
            "continuation": self.continuationKey
        }

    def parse_source(self):
        self.fullResponse = self.response.json()
        self.responseSource = getValue(self.fullResponse, [
            "onResponseReceivedEndpoints",
            0 if self.isNextRequest else 1,
            "appendContinuationItemsAction" if self.isNextRequest else "reloadContinuationItemsCommand",
            "continuationItems",
        ])

    def parse_continuation_source(self):
        self.continuationKey = getValue(
            self.response.json(),
            [
                "contents",
                "twoColumnWatchNextResults",
                "results",
                "results",
                "contents",
                -1,
                "itemSectionRenderer",
                "contents",
                0,
                "continuationItemRenderer",
                "continuationEndpoint",
                "continuationCommand",
                "token",
            ]
        )

    def sync_make_comment_request(self):
        self.prepare_comments_request()
        self.response = self.syncPostRequest()
        if self.response.status_code == 200:
            self.parse_source()

    def sync_make_continuation_request(self):
        self.prepare_continuation_request()
        self.response = self.syncPostRequest()
        if self.response.status_code == 200:
            self.parse_continuation_source()
            if not self.continuationKey:
                raise Exception("Could not retrieve continuation token")
        else:
            raise Exception("Status code is not 200")

    async def async_make_comment_request(self):
        self.prepare_comments_request()
        self.response = await self.asyncPostRequest()
        if self.response.status_code == 200:
            self.parse_source()

    async def async_make_continuation_request(self):
        self.prepare_continuation_request()
        self.response = await self.asyncPostRequest()
        if self.response.status_code == 200:
            self.parse_continuation_source()
            if not self.continuationKey:
                raise Exception("Could not retrieve continuation token")
        else:
            raise Exception("Status code is not 200")

    def sync_create(self):
        self.sync_make_continuation_request()
        self.sync_make_comment_request()
        self.__getComponents()

    def sync_create_next(self):
        self.isNextRequest = True
        self.sync_make_comment_request()
        self.__getComponents()

    async def async_create(self):
        await self.async_make_continuation_request()
        await self.async_make_comment_request()
        self.__getComponents()

    async def async_create_next(self):
        self.isNextRequest = True
        await self.async_make_comment_request()
        self.__getComponents()

    def __buildMutationsMap(self) -> dict:
        """Build a lookup map of commentEntityPayload by commentId from mutations."""
        mutations_map = {}
        if not self.fullResponse:
            return mutations_map
        mutations = self.__getValue(self.fullResponse, [
            "frameworkUpdates", "entityBatchUpdate", "mutations"
        ])
        if mutations:
            for mutation in mutations:
                payload = self.__getValue(mutation, ["payload", "commentEntityPayload"])
                if payload:
                    comment_id = self.__getValue(payload, ["properties", "commentId"])
                    if comment_id:
                        mutations_map[comment_id] = payload
        return mutations_map

    def __parseNewApiComment(self, payload: dict) -> dict:
        """Parse comment from new commentEntityPayload structure."""
        properties = payload.get("properties", {})
        author = payload.get("author", {})
        toolbar = payload.get("toolbar", {})

        avatar_url = author.get("avatarThumbnailUrl")
        thumbnails = [{"url": avatar_url}] if avatar_url else []

        return {
            "id": properties.get("commentId"),
            "author": {
                "id": author.get("channelId"),
                "name": author.get("displayName"),
                "thumbnails": thumbnails
            },
            "content": self.__getValue(properties, ["content", "content"]),
            "published": properties.get("publishedTime"),
            "isLiked": False,
            "authorIsChannelOwner": author.get("isCreator", False),
            "voteStatus": "INDIFFERENT",
            "votes": {
                "simpleText": toolbar.get("likeCountNotliked"),
                "label": toolbar.get("likeCountA11y")
            },
            "replyCount": toolbar.get("replyCount"),
        }

    def __parseOldApiComment(self, comment: dict) -> dict:
        """Parse comment from old commentRenderer structure (fallback)."""
        return {
            "id": self.__getValue(comment, ["commentId"]),
            "author": {
                "id": self.__getValue(comment, ["authorEndpoint", "browseEndpoint", "browseId"]),
                "name": self.__getValue(comment, ["authorText", "simpleText"]),
                "thumbnails": self.__getValue(comment, ["authorThumbnail", "thumbnails"])
            },
            "content": self.__getValue(comment, ["contentText", "runs", 0, "text"]),
            "published": self.__getValue(comment, ["publishedTimeText", "runs", 0, "text"]),
            "isLiked": self.__getValue(comment, ["isLiked"]),
            "authorIsChannelOwner": self.__getValue(comment, ["authorIsChannelOwner"]),
            "voteStatus": self.__getValue(comment, ["voteStatus"]),
            "votes": {
                "simpleText": self.__getValue(comment, ["voteCount", "simpleText"]),
                "label": self.__getValue(comment, ["voteCount", "accessibility", "accessibilityData", "label"])
            },
            "replyCount": self.__getValue(comment, ["replyCount"]),
        }

    def __getComponents(self) -> None:
        comments = []
        mutations_map = self.__buildMutationsMap()

        for item in self.responseSource:
            comment_thread = self.__getValue(item, ["commentThreadRenderer"])
            if not comment_thread:
                continue

            # Try NEW API structure first (commentViewModel + mutations)
            view_model = self.__getValue(comment_thread, ["commentViewModel", "commentViewModel"])
            if view_model and mutations_map:
                comment_id = self.__getValue(view_model, ["commentId"])
                payload = mutations_map.get(comment_id)
                if payload:
                    try:
                        comments.append(self.__parseNewApiComment(payload))
                    except:
                        pass
            else:
                # OLD API fallback: commentRenderer structure
                comment = self.__getValue(comment_thread, ["comment", "commentRenderer"])
                if comment:
                    try:
                        comments.append(self.__parseOldApiComment(comment))
                    except:
                        pass

        self.commentsComponent["result"].extend(comments)
        self.continuationKey = self.__getValue(self.responseSource, [-1, "continuationItemRenderer", "continuationEndpoint", "continuationCommand", "token"])

    def __result(self, mode: int) -> Union[dict, str]:
        if mode == ResultMode.dict:
            return self.commentsComponent
        elif mode == ResultMode.json:
            return json.dumps(self.commentsComponent, indent=4)

    def __getValue(self, source: dict, path: Iterable[str]) -> Union[str, int, dict, None]:
        value = source
        for key in path:
            if type(key) is str:
                if key in value.keys():
                    value = value[key]
                else:
                    value = None
                    break
            elif type(key) is int:
                if len(value) != 0:
                    value = value[key]
                else:
                    value = None
                    break
        return value

    def __getAllWithKey(self, source: Iterable[Mapping[K, T]], key: K) -> Iterable[T]:
        for item in source:
            if key in item:
                yield item[key]

    def __getValueEx(self, source: dict, path: List[str]) -> Iterable[Union[str, int, dict, None]]:
        if len(path) <= 0:
            yield source
            return
        key = path[0]
        upcoming = path[1:]
        if key is None:
            following_key = upcoming[0]
            upcoming = upcoming[1:]
            if following_key is None:
                raise Exception("Cannot search for a key twice consecutive or at the end with no key given")
            values = self.__getAllWithKey(source, following_key)
            for val in values:
                yield from self.__getValueEx(val, path=upcoming)
        else:
            val = self.__getValue(source, path=[key])
            yield from self.__getValueEx(val, path=upcoming)

    def __getFirstValue(self, source: dict, path: Iterable[str]) -> Union[str, int, dict, None]:
        values = self.__getValueEx(source, list(path))
        for val in values:
            if val is not None:
                return val
        return None
