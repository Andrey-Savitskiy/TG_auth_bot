import logging
import random
import sqlite3
import os
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types.chat_permissions import ChatPermissions
from aiogram.utils.exceptions import BotBlocked
from dotenv import load_dotenv
from datetime import datetime, timedelta


load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
KICK_TIME = os.getenv('KICK_TIME')


bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)


def db_handler(command: str):
    conn = sqlite3.connect("sqlite3.db")
    cursor = conn.cursor()
    cursor.execute(command)
    conn.commit()
    cursor.close()


def db_select_handler(command: str, clear: bool = False):
    conn = sqlite3.connect("sqlite3.db")
    cursor = conn.cursor()
    cursor.execute(command)
    if clear:
        result = cursor.fetchall()
    else:
        result = cursor.fetchone()
    conn.commit()
    cursor.close()
    return result


def generating_an_equation(user_id: int, chat_name: str) -> str:
    number_one = random.randint(0, 10)
    number_two = random.randint(5, 10)
    number_three = random.randint(0, 5)
    result = number_one + number_two - number_three
    db_handler(f"UPDATE users SET result = {result} WHERE id = {user_id};")
    text = f'Для получения возможности писать в чате "{chat_name}", ' \
           f'необходимо вычислить значение выражения:\n' \
           f'{number_one} + {number_two} - {number_three} = ?'

    return text


@dp.errors_handler(exception=BotBlocked)
async def error_bot_blocked(update: types.Update, exception: BotBlocked):
    db_handler(f"INSERT INTO logs(log, time) VALUES ('{exception.text}',"
               f"'{datetime.now().strftime('%d.%m.%Y %H:%M')}')")
    return True


@dp.message_handler(content_types=['new_chat_members'])
async def on_user_joined(message: types.Message):
    await message.delete()
    user_id = message.from_user['id']
    chat_id = message['chat']['id']
    chat_name = message['chat']['title']
    db_handler(f"INSERT INTO users(id, created_at_time, chat_id)"
               f"VALUES ({user_id}, '{message['date'].strftime('%d.%m.%Y %H:%M')}', {chat_id})")
    text = generating_an_equation(user_id, chat_name)
    await bot.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))
    await bot.send_message(chat_id=user_id, text=text)


@dp.message_handler(content_types=['left_chat_member'])
async def on_user_joined(message: types.Message):
    await message.delete()
    user_id = message.from_user['id']
    db_handler(f"DELETE FROM users WHERE id = {user_id}")


@dp.message_handler()
async def cmd_test2(message: types.Message):
    chat_type = message['chat']['type']
    try:
        if chat_type == 'private':
            text = message['text']
            user_id = message.from_user['id']

            is_auth, result, chat_id = db_select_handler(f"SELECT is_auth, result, chat_id "
                                                         f"FROM users WHERE id = {user_id}")
            if is_auth == 0:
                if str(result) == text:
                    db_handler(f"UPDATE users SET is_auth = 1, result = NULL WHERE id = {user_id};")
                    await bot.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=True))
                    await message.answer('Ответ верный, теперь вы можете писать в группе.')
                else:
                    await message.answer('Ответ неверный. Попробуйте еще раз.')
    except TypeError:
        return True


async def cleaner_dead_users(wait_for: int):
    while True:
        try:
            await asyncio.sleep(wait_for)
            now = datetime.now()
            delta = (now - timedelta(minutes=int(KICK_TIME))).strftime('%d.%m.%Y %H:%M')

            result = db_select_handler(f"SELECT id, chat_id FROM users "
                               f"WHERE created_at_time < '{delta}' AND is_auth == 0", clear=True)

            for user in result:
                user_id = user[0]
                chat_id = user[1]
                db_handler(f"DELETE FROM users WHERE id = {user_id}")
                await bot.kick_chat_member(chat_id=chat_id, user_id=user_id)
                await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
        except:
            continue


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(cleaner_dead_users(15)) # секунды
    executor.start_polling(dp, skip_updates=True)
