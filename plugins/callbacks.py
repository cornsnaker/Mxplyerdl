from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from core.database import add_to_queue
from plugins.handlers import DownloadState

router = Router()

@router.callback_query(DownloadState.waiting_for_selection, F.data.startswith("qual:"))
async def callbacks_quality(callback: types.CallbackQuery, state: FSMContext):
    # User selected a quality. Store it in state.
    quality = callback.data.split(":")[1]
    await state.update_data(pref_quality=quality)
    await callback.answer(f"Quality set to {quality}")

@router.callback_query(DownloadState.waiting_for_selection, F.data == "dl_one")
async def callbacks_dl_one(callback: types.CallbackQuery, state: FSMContext, bot):
    data = await state.get_data()
    url = data['url']
    title = data['title']
    season = data['season']
    episode = data['episode']
    pref_quality = data.get('pref_quality', 'best')
    user_id = callback.from_user.id

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Added to queue!")

    await add_to_queue(user_id, url, title, season, episode, quality=pref_quality)
    await callback.message.edit_text(f"✅ Episode added to queue: {title} S{season}E{episode} [{pref_quality}]")
    await state.clear()

@router.callback_query(DownloadState.waiting_for_selection, F.data == "dl_batch")
async def callbacks_dl_batch(callback: types.CallbackQuery, state: FSMContext, bot):
    data = await state.get_data()
    links = data['links']
    title = data['title']
    season = data['season']
    pref_quality = data.get('pref_quality', 'best')
    user_id = callback.from_user.id

    await callback.answer(f"Adding {len(links)} episodes to queue...")

    for i, link in enumerate(links):
        await add_to_queue(user_id, link, f"{title} (Part {i+1})", season, 0, quality=pref_quality)

    await callback.message.edit_text(f"✅ Added {len(links)} episodes to queue. They will be processed shortly.")
    await state.clear()
