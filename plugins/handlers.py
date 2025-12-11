from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.mx_api import fetch, extract_title, extract_season_episode, gather_episode_links, get_m3u8, parse_master_playlist, extract_thumbnail
from core.database import add_user

router = Router()

class DownloadState(StatesGroup):
    waiting_for_selection = State()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await message.answer("👋 Welcome to MX Downloader Bot!\nSend me an MX Player link to start.")

@router.message(F.text.contains("mxplayer.in"))
async def handle_link(message: types.Message, state: FSMContext):
    url = message.text.strip()
    status = await message.answer("🔍 Analyzing link...")

    html = await fetch(url)
    title = extract_title(html)
    thumb = extract_thumbnail(html)
    s, e = extract_season_episode(html)
    links = await gather_episode_links(url, html)
    m3u8 = await get_m3u8(html)

    # Parse quality options
    qualities = []
    if m3u8:
        try:
            m3u8_text = await fetch(m3u8)
            variants = await parse_master_playlist(m3u8_text)
            # Sort by resolution height or bandwidth
            variants.sort(key=lambda x: x.get('bandwidth', 0), reverse=True)
            seen_res = set()
            for v in variants:
                res = v.get('resolution')
                if res and res not in seen_res:
                    qualities.append(res)
                    seen_res.add(res)
        except:
            pass

    caption = (
        f"🎬 **Title:** {title}\n"
        f"📅 **Season:** {s} | **Episode:** {e}\n"
        f"🔗 **Links Found:** {len(links)}"
    )

    builder = InlineKeyboardBuilder()

    # Add quality buttons (row 1)
    if qualities:
        row = []
        for q in qualities[:3]: # limit to top 3
            # q is "1920x1080"
            label = q.split('x')[1] + "p"
            row.append(types.InlineKeyboardButton(text=label, callback_data=f"qual:{label}"))
        builder.row(*row)

    builder.row(types.InlineKeyboardButton(text="⬇️ Download This Episode", callback_data="dl_one"))

    if len(links) > 1:
        builder.row(types.InlineKeyboardButton(text="📦 Batch Download Season", callback_data="dl_batch"))

    await status.delete()
    if thumb:
        await message.answer_photo(thumb, caption=caption, reply_markup=builder.as_markup())
    else:
        await message.answer(caption, reply_markup=builder.as_markup())

    # Save state
    await state.set_state(DownloadState.waiting_for_selection)
    await state.update_data(url=url, title=title, season=s, episode=e, links=links)
