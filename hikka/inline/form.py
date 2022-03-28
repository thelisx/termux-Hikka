from .types import InlineUnit
from .. import utils

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineQuery,
)

from aiogram.utils.exceptions import (
    MessageNotModified,
    RetryAfter,
    MessageIdInvalid,
    InvalidQueryID,
)

from typing import Union, List, Any
from types import FunctionType
from telethon.tl.types import Message
import logging
import asyncio
import time

logger = logging.getLogger(__name__)


class ListGalleryHelper:
    def __init__(self, lst: List[str]):
        self.lst = lst

    def __call__(self):
        elem = self.lst[-1]
        del self.lst[-1]
        return elem


class Form(InlineUnit):
    async def form(
        self,
        text: str,
        message: Union[Message, int],
        reply_markup: List[List[dict]] = None,
        force_me: bool = True,
        always_allow: Union[List[list], None] = None,
        ttl: Union[int, bool] = False,
        on_unload: Union[FunctionType, None] = None,
    ) -> Union[str, bool]:
        """Creates inline form with callback
        Args:
                text
                        Content of inline form. HTML markdown supported
                message
                        Where to send inline. Can be either `Message` or `int`
                reply_markup
                        List of buttons to insert in markup. List of dicts with
                        keys: text, callback
                force_me
                        Either this form buttons must be pressed only by owner scope or no
                always_allow
                        Users, that are allowed to press buttons in addition to previous rules
                ttl
                        Time, when the form is going to be unloaded. Unload means, that the form
                        buttons with inline queries and callback queries will become unusable, but
                        buttons with type url will still work as usual. Pay attention, that ttl can't
                        be bigger, than default one (1 day) and must be either `int` or `False`
                on_unload
                    Callback, called when form is unloaded and/or closed. You can clean up trash
                    or perform another needed action
        """

        if reply_markup is None:
            reply_markup = []

        if always_allow is None:
            always_allow = []

        if not isinstance(text, str):
            logger.error("Invalid type for `text`")
            return False

        if not isinstance(message, (Message, int)):
            logger.error("Invalid type for `message`")
            return False

        if not isinstance(reply_markup, list):
            logger.error("Invalid type for `reply_markup`")
            return False

        if not all(
            all(isinstance(button, dict) for button in row) for row in reply_markup
        ):
            logger.error("Invalid type for one of the buttons. It must be `dict`")
            return False

        if not all(
            all(
                "url" in button
                or "callback" in button
                or "input" in button
                or "data" in button
                for button in row
            )
            for row in reply_markup
        ):
            logger.error(
                "Invalid button specified. "
                "Button must contain one of the following fields:\n"
                "  - `url`\n"
                "  - `callback`\n"
                "  - `input`\n"
                "  - `data`"
            )
            return False

        if not isinstance(force_me, bool):
            logger.error("Invalid type for `force_me`")
            return False

        if not isinstance(always_allow, list):
            logger.error("Invalid type for `always_allow`")
            return False

        if not isinstance(ttl, int) and ttl:
            logger.error("Invalid type for `ttl`")
            return False

        if isinstance(ttl, int) and (ttl > self._markup_ttl or ttl < 10):
            ttl = self._markup_ttl
            logger.debug("Defaulted ttl, because it breaks out of limits")

        form_uid = utils.rand(30)

        self._forms[form_uid] = {
            "text": text,
            "buttons": reply_markup,
            "ttl": round(time.time()) + ttl or self._markup_ttl,
            "force_me": force_me,
            "always_allow": always_allow,
            "chat": None,
            "message_id": None,
            "uid": form_uid,
            "on_unload": on_unload,
        }

        try:
            q = await self._client.inline_query(self.bot_username, form_uid)
            m = await q[0].click(
                utils.get_chat_id(message) if isinstance(message, Message) else message,
                reply_to=message.reply_to_msg_id
                if isinstance(message, Message)
                else None,
            )
        except Exception:
            msg = (
                "🚫 <b>A problem occurred with inline bot "
                "while processing query. Check logs for "
                "further info.</b>"
            )

            del self._forms[form_uid]
            if isinstance(message, Message):
                await (message.edit if message.out else message.respond)(msg)
            else:
                await self._client.send_message(message, msg)

            return False

        self._forms[form_uid]["chat"] = utils.get_chat_id(m)
        self._forms[form_uid]["message_id"] = m.id
        if isinstance(message, Message):
            await message.delete()

        if not any(
            any("callback" in button or "input" in button for button in row)
            for row in reply_markup
        ):
            del self._forms[form_uid]
            logger.debug(
                f"Unloading form {form_uid}, because it " "doesn't contain callbacks"
            )

        return form_uid

    def _generate_markup(self, form_uid: Union[str, list]) -> InlineKeyboardMarkup:
        """Generate markup for form"""
        markup = InlineKeyboardMarkup()

        for row in (
            self._forms[form_uid]["buttons"] if isinstance(form_uid, str) else form_uid
        ):
            for button in row:
                if "callback" in button and "_callback_data" not in button:
                    button["_callback_data"] = utils.rand(30)

                if "input" in button and "_switch_query" not in button:
                    button["_switch_query"] = utils.rand(10)

        for row in (
            self._forms[form_uid]["buttons"] if isinstance(form_uid, str) else form_uid
        ):
            line = []
            for button in row:
                try:
                    if "url" in button:
                        line += [
                            InlineKeyboardButton(
                                button["text"],
                                url=button.get("url", None),
                            )
                        ]
                    elif "callback" in button:
                        line += [
                            InlineKeyboardButton(
                                button["text"],
                                callback_data=button["_callback_data"],
                            )
                        ]
                    elif "input" in button:
                        line += [
                            InlineKeyboardButton(
                                button["text"],
                                switch_inline_query_current_chat=button["_switch_query"] + " ",  # fmt: skip
                            )
                        ]
                    elif "data" in button:
                        line += [
                            InlineKeyboardButton(
                                button["text"],
                                callback_data=button["data"],
                            )
                        ]
                    else:
                        logger.warning(
                            "Button have not been added to "
                            "form, because it is not structured "
                            f"properly. {button}"
                        )
                except KeyError:
                    logger.exception(
                        "Error while forming markup! Probably, you "
                        "passed wrong type combination for button. "
                        "Contact developer of module."
                    )
                    return False

            markup.row(*line)

        return markup

    async def _callback_query_edit(
        self,
        text: str,
        reply_markup: List[List[dict]] = None,
        force_me: Union[bool, None] = None,
        always_allow: Union[List[int], None] = None,
        query: Any = None,
        form: Any = None,
        form_uid: Any = None,
        inline_message_id: Union[str, None] = None,
        disable_web_page_preview: bool = True,
    ) -> None:
        """Do not edit or pass `self`, `query`, `form`, `form_uid` params, they are for internal use only"""
        if reply_markup is None:
            reply_markup = []

        if not isinstance(text, str):
            logger.error("Invalid type for `text`")
            return False

        if isinstance(reply_markup, list):
            form["buttons"] = reply_markup
        if isinstance(force_me, bool):
            form["force_me"] = force_me
        if isinstance(always_allow, list):
            form["always_allow"] = always_allow
        try:
            await self.bot.edit_message_text(
                text,
                inline_message_id=inline_message_id or query.inline_message_id,
                parse_mode="HTML",
                disable_web_page_preview=disable_web_page_preview,
                reply_markup=self._generate_markup(form_uid),
            )
        except MessageNotModified:
            try:
                await query.answer()
            except InvalidQueryID:
                pass  # Just ignore that error, bc we need to just
                # remove preloader from user's button, if message
                # was deleted

        except RetryAfter as e:
            logger.info(f"Sleeping {e.timeout}s on aiogram FloodWait...")
            await asyncio.sleep(e.timeout)
            return await self._callback_query_edit(
                text,
                reply_markup,
                force_me,
                always_allow,
                query,
                form,
                form_uid,
                inline_message_id,
            )
        except MessageIdInvalid:
            try:
                await query.answer(
                    "I should have edited some message, but it is deleted :("
                )
            except InvalidQueryID:
                pass  # Just ignore that error, bc we need to just
                # remove preloader from user's button, if message
                # was deleted

    async def _callback_query_delete(
        self,
        form: Any = None,
        form_uid: Any = None,
    ) -> bool:
        """Params `self`, `form`, `form_uid` are for internal use only, do not try to pass them"""
        try:
            await self._client.delete_messages(form["chat"], [form["message_id"]])

            if callable(self._forms[form_uid]["on_unload"]):
                self._forms[form_uid]["on_unload"]()

            del self._forms[form_uid]
        except Exception:
            return False

        return True

    async def _callback_query_unload(self, form_uid: Any = None) -> bool:
        """Params `self`, `form_uid` are for internal use only, do not try to pass them"""
        try:
            if callable(self._forms[form_uid]["on_unload"]):
                self._forms[form_uid]["on_unload"]()

            del self._forms[form_uid]
        except Exception:
            return False

        return True

    async def _form_inline_handler(self, inline_query: InlineQuery) -> None:
        for form in self._forms.copy().values():
            for button in utils.array_sum(form.get("buttons", [])):
                if (
                    "_switch_query" in button
                    and "input" in button
                    and button["_switch_query"] == inline_query.query.split()[0]
                    and inline_query.from_user.id
                    in [self._me]
                    + self._client.dispatcher.security._owner
                    + form["always_allow"]
                ):
                    await inline_query.answer(
                        [
                            InlineQueryResultArticle(
                                id=utils.rand(20),
                                title=button["input"],
                                description="⚠️ Please, do not remove identifier!",
                                input_message_content=InputTextMessageContent(
                                    "🔄 <b>Transferring value to userbot...</b>\n"
                                    "<i>This message is gonna be deleted...</i>",
                                    "HTML",
                                    disable_web_page_preview=True,
                                ),
                            )
                        ],
                        cache_time=60,
                    )
                    return

        if inline_query.query not in self._forms:
            return

        # Otherwise, answer it with templated form
        await inline_query.answer(
            [
                InlineQueryResultArticle(
                    id=utils.rand(20),
                    title="Hikka",
                    input_message_content=InputTextMessageContent(
                        self._forms[inline_query.query]["text"],
                        "HTML",
                        disable_web_page_preview=True,
                    ),
                    reply_markup=self._generate_markup(inline_query.query),
                )
            ],
            cache_time=60,
        )