"""API reference pages. Signatures and examples are read from the library itself (docstrings), so they never drift;
the one-line descriptions here are translated.

Format of SPEC (one block per page):
    @page-id  python.module:Object  prefix          ← prefix is how the object is written in code (ctx, bot, req…)
    # Group title uz | ru | en
    member | uz | ru | en
    !raw text | uz | ru | en                        ← a row without introspection (e.g. nicebot.js functions)
"""
from __future__ import annotations

SPEC = r"""
@ref-ctx nicebot.context:Context ctx
# Ma'lumot o'qish | Чтение данных | Reading the update
message | Kelgan xabar (yoki tugmasi bosilgan xabar) | Входящее сообщение (или сообщение с нажатой кнопкой) | The incoming message (or the one whose button was pressed)
text | Xabar matni, izohi yoki inline so'rov matni | Текст, подпись или текст inline-запроса | Text, caption or inline query text
user | Yuboruvchining bazadagi yozuvi | Запись отправителя в базе | The sender's database row
user_id | Yuboruvchining Telegram id'si | Telegram id отправителя | The sender's Telegram id
from_user | Telegram'dagi User obyekti | Объект User из Telegram | The Telegram User object
name | Yuboruvchining ismi | Имя отправителя | The sender's first name
mention | Yuboruvchiga bosiladigan havola (HTML) | Кликабельное упоминание (HTML) | Clickable mention (HTML)
chat | Joriy chat | Текущий чат | The current chat
chat_id | Joriy chat id'si | Id текущего чата | Id of the current chat
command | Buyruq nomi (/ siz) | Имя команды (без /) | Command name (without /)
args | Buyruqdan keyingi so'zlar | Слова после команды | Words after the command
arg | Buyruqdan keyingi butun matn | Весь текст после команды | Everything after the command
payload | Deep-link parametri | Параметр deep-link | Deep-link payload
data | Bosilgan tugmaning callback_data'si | callback_data нажатой кнопки | callback_data of the pressed button
callback | Tugma bosilishi (CallbackQuery) | Нажатие кнопки (CallbackQuery) | The button press (CallbackQuery)
inline_query | Inline so'rov | Inline-запрос | The inline query
media | Xabardagi fayl (Media) | Файл в сообщении (Media) | The file in the message (Media)
album_media | Albomdagi barcha fayllar | Все файлы альбома | Every file of an album
web_app_data | Mini App sendData() ma'lumoti | Данные sendData() из Mini App | Data from a Mini App's sendData()
is_private | Shaxsiy chatmi | Личный ли чат | Is it a private chat
is_group | Guruhmi | Группа ли | Is it a group
is_callback | Tugma bosilganmi | Нажатие ли кнопки | Is it a button press
is_admin | Bot adminimi | Админ ли бота | Is the sender a bot admin
lang | Foydalanuvchi tili | Язык пользователя | The user's language
ref_link | Foydalanuvchining referal havolasi | Реферальная ссылка пользователя | The user's referral link
params | Shablon va regex parametrlari | Параметры шаблона и regex | Template and regex parameters
match | Regex natijasi | Результат regex | The regex match
album | Albom xabarlari | Сообщения альбома | Messages of an album
value | Toggle yoki tugma qiymati | Значение Toggle или кнопки | Value of a Toggle or button
extra | Middleware'lar uchun erkin lug'at | Свободный словарь для middleware | Free dict for middlewares
elapsed | Update kelganidan beri o'tgan vaqt | Время с прихода апдейта | Seconds since the update arrived
bot | Bot obyekti | Объект бота | The bot object
update | Xom Update | Сырой Update | The raw Update
event | Update ichidagi obyekt | Объект внутри Update | The update payload
event_name | Update turi | Тип апдейта | The update type
# Yuborish | Отправка | Sending
reply | Matnli xabar yuborish | Отправить текстовое сообщение | Send a text message
send | reply bilan bir xil | То же, что reply | Same as reply
send_to | Boshqa chatga yuborish | Отправить в другой чат | Send to another chat
photo | Rasm yuborish | Отправить фото | Send a photo
video | Video yuborish | Отправить видео | Send a video
document | Fayl yuborish | Отправить файл | Send a file
audio | Musiqa yuborish | Отправить музыку | Send music
voice | Ovozli xabar yuborish | Отправить голосовое | Send a voice message
animation | GIF yuborish | Отправить GIF | Send a GIF
sticker | Stiker yuborish | Отправить стикер | Send a sticker
video_note | Dumaloq video yuborish | Отправить кружок | Send a round video
send_file | Turini o'zi aniqlab yuborish | Отправить с автоопределением типа | Send, detecting the kind
media_group | Albom yuborish | Отправить альбом | Send an album
location | Joylashuv yuborish | Отправить геолокацию | Send a location
venue | Manzil yuborish | Отправить место | Send a venue
contact | Kontakt yuborish | Отправить контакт | Send a contact
poll | So'rovnoma yuborish | Отправить опрос | Send a poll
quiz | Viktorina yuborish | Отправить викторину | Send a quiz
dice | Kubik tashlash | Бросить кубик | Throw a dice
action | "yozmoqda…" kabi status | Статус вроде «печатает…» | A status such as "typing…"
forward | Xabarni forward qilish | Переслать сообщение | Forward the message
copy | Xabar nusxasini yuborish | Отправить копию сообщения | Copy the message
# Tahrirlash | Редактирование | Editing
edit | Xabarni tahrirlash | Изменить сообщение | Edit the message
edit_buttons | Faqat tugmalarni almashtirish | Заменить только кнопки | Replace only the buttons
edit_media | Rasm/video/faylni almashtirish | Заменить фото/видео/файл | Replace the photo/video/file
respond | Tugmadan bo'lsa tahrirlash, aks holda yuborish | Изменить при нажатии, иначе отправить | Edit after a button press, otherwise send
delete | Xabarni o'chirish | Удалить сообщение | Delete the message
pin | Xabarni qadash | Закрепить сообщение | Pin the message
unpin | Qadashni olish | Открепить | Unpin
react | Reaksiya qo'yish | Поставить реакцию | Put a reaction
# Tugma va inline | Кнопки и inline | Buttons and inline
answer | Tugmaga qisqa javob | Короткий ответ на нажатие | A toast for the pressed button
alert | Tugmaga oyna bilan javob | Ответ всплывающим окном | A popup for the pressed button
answer_inline | Inline so'rovga javob | Ответ на inline-запрос | Answer an inline query
# Fayllar | Файлы | Files
download | Faylni xotiraga yuklab olish | Скачать файл в память | Download a file into memory
save | Faylni diskka saqlash | Сохранить файл на диск | Save a file to disk
# Suhbatlar | Диалоги | Conversations
ask | Savol berib javob kutish | Задать вопрос и ждать ответ | Ask and wait for the answer
confirm | Ha/Yo'q savol | Вопрос Да/Нет | A yes/no question
choose | Variant tanlatish | Выбор варианта | Pick one or several options
form | Bir nechta savol ketma-ket | Несколько вопросов подряд | Several questions in a row
wait_message | Keyingi xabarni kutish | Ждать следующее сообщение | Wait for the next message
# Holat va sozlamalar | Состояние и настройки | State and settings
set_state | Holatni o'rnatish | Установить состояние | Set the state
get_state | Joriy holat | Текущее состояние | The current state
state_data | Holat ma'lumotlari | Данные состояния | State data
update_data | Holatga ma'lumot qo'shish | Добавить данные в состояние | Add data to the state
clear_state | Holatni tozalash | Очистить состояние | Clear the state
setting | Foydalanuvchi sozlamasini o'qish | Прочитать настройку пользователя | Read a user setting
set_setting | Foydalanuvchi sozlamasini saqlash | Сохранить настройку пользователя | Save a user setting
# Tarjima | Перевод | Translations
t | Kalitni tarjima qilish | Перевести ключ | Translate a key
set_lang | Foydalanuvchi tilini saqlash | Сохранить язык пользователя | Save the user's language
# Menyu va to'lov | Меню и оплата | Menus and payments
menu | Ko'p darajali menyu | Многоуровневое меню | A multi-level menu
paginate | Sahifalab ko'rsatish | Постраничный вывод | Show a list page by page
invoice | Telegram Stars hisob-fakturasi | Счёт в Telegram Stars | A Telegram Stars invoice
refund | To'lovni qaytarish | Вернуть платёж | Refund a payment
# Guruhlar | Группы | Groups
ban | Ban qilish | Забанить | Ban a member
unban | Bandan chiqarish | Разбанить | Unban
kick | Guruhdan chiqarish | Исключить из группы | Remove from the group
mute | Yozishni taqiqlash | Запретить писать | Mute
unmute | Yozishga ruxsat | Разрешить писать | Unmute
warn | Ogohlantirish | Предупреждение | Warn
is_member | Kanal/guruh a'zosimi | Состоит ли в канале/группе | Is a member of a chat
is_chat_admin | Guruh adminimi | Админ ли группы | Is a group admin
# Boshqa | Прочее | Other
background | Fon vazifasi | Фоновая задача | Background task
notify_admins | Adminlarga xabar | Сообщение админам | Message the admins

@ref-bot nicebot.bot:Nicebot bot
# Ishga tushirish | Запуск | Running
start | Botni ishga tushirish | Запустить бота | Run the bot
run | Async ishga tushirish | Асинхронный запуск | Async entry point
stop | To'xtatish | Остановить | Stop
shutdown | To'g'ri yopish | Корректно завершить | Shut down gracefully
from_env | .env faylidan yaratish | Создать из .env | Create from .env
run_all | Bir nechta botni birga | Несколько ботов вместе | Several bots together
test | Telegram'siz test | Тест без Telegram | Test without Telegram
setup | Ulanish va sozlash | Подключение и настройка | Connect and prepare
# Handlerlar | Обработчики | Handlers
command | /buyruq | /команда | /command
text | Matnli xabarlar | Текстовые сообщения | Text messages
on | Kontent turi bo'yicha | По типу контента | By content type
message | Filtrlar bilan xabar | Сообщения с фильтрами | Messages with filters
callback | Tugma bosilishi | Нажатие кнопки | Button presses
inline | Inline so'rov | Inline-запрос | Inline queries
album | Albom | Альбом | Albums
fallback | Hech narsa mos kelmasa | Если ничего не подошло | When nothing matched
deep_link | /start parametri | Параметр /start | /start payload
edited | Tahrirlangan xabar | Изменённое сообщение | Edited messages
channel | Kanal posti | Пост в канале | Channel posts
join | Guruhga qo'shildi | Вступил в группу | Joined a group
leave | Guruhdan chiqdi | Вышел из группы | Left a group
webapp_data | Mini App sendData() | Mini App sendData() | Mini App sendData()
paid | Muvaffaqiyatli to'lov | Успешная оплата | Successful payment
pre_checkout | To'lovdan oldin tekshirish | Проверка перед оплатой | Check before payment
chosen_inline | Tanlangan inline natija | Выбранный inline-результат | Chosen inline result
my_chat_member | Bot holati o'zgardi | Изменился статус бота | The bot's status changed
chat_member | A'zo holati o'zgardi | Изменился статус участника | A member's status changed
join_request | Qo'shilish so'rovi | Заявка на вступление | Join request
reaction | Reaksiya | Реакция | Reaction
poll_answer | So'rovnomaga ovoz | Голос в опросе | Poll answer
event | Istalgan update turi | Любой тип апдейта | Any update type
error | Xatolarni ushlash | Обработка ошибок | Error handlers
include | Router qo'shish | Подключить Router | Add routers
middleware | Middleware | Middleware | Middleware
provide | DI qiymati | Значение для DI | A DI value
on_startup | Ishga tushganda | При запуске | On startup
on_shutdown | To'xtaganda | При остановке | On shutdown
on_new_user | Yangi foydalanuvchi | Новый пользователь | New user
on_referral | Referal orqali kelgan | Пришёл по рефералке | Came via referral
# Mini App | Mini App | Mini Apps
api | Backend endpoint | Эндпоинт бэкенда | Backend endpoint
webapp | Statik fayllar | Статические файлы | Static files
menu_app | Menyu tugmasi (ishga tushganda) | Кнопка меню (при запуске) | Menu button (on start)
set_menu_app | Menyu tugmasini hozir o'rnatish | Установить кнопку меню сейчас | Set the menu button now
webapp_url | To'liq Mini App manzili | Полный адрес Mini App | Full Mini App URL
app_link | t.me/bot/app havolasi | Ссылка t.me/bot/app | t.me/bot/app link
public_url | Ommaviy HTTPS manzil | Публичный HTTPS-адрес | Public HTTPS address
# Havolalar | Ссылки | Links
start_link | /start havolasi | Ссылка с /start | /start link
ref_link | Referal havola | Реферальная ссылка | Referral link
# Fayllar | Файлы | Files
download_file | Faylni yuklab olish | Скачать файл | Download a file
save_file | Faylni diskka saqlash | Сохранить файл на диск | Save a file to disk
# Biznes | Бизнес | Business
broadcast | Hammaga xabar | Рассылка | Message everyone
stats | Statistika | Статистика | Statistics
maintenance | Texnik ishlar rejimi | Режим техработ | Maintenance mode
notify_admins | Adminlarga xabar | Сообщение админам | Message the admins
User | Foydalanuvchilar modeli | Модель пользователей | The users model
get_setting | Sozlamani o'qish | Прочитать настройку | Read a setting
set_setting | Sozlamani saqlash | Сохранить настройку | Save a setting
# Vazifalar | Задачи | Jobs
every | Har N vaqtda | Каждые N времени | Every N
at | Har kuni soatda | Каждый день в час | Daily at a time
later | Keyinroq bajarish | Выполнить позже | Run later
background | Fon vazifasi | Фоновая задача | Background task
# Past daraja | Низкий уровень | Low level
request | Istalgan API metodini chaqirish | Вызвать любой метод API | Call any API method
feed | Update berish | Передать апдейт | Feed an update
process_update | Update'ni yo'naltirish | Маршрутизировать апдейт | Route an update
safe_delete | Xatosiz o'chirish | Удалить без ошибок | Delete without errors
flush_stats | Statistikani yozish | Записать статистику | Write statistics
allowed_updates | So'raladigan update turlari | Запрашиваемые типы апдейтов | Requested update types
close | shutdown bilan bir xil | То же, что shutdown | Same as shutdown
close_bot_instance | Telegram'ning close metodi | Метод close Telegram | Telegram's close method
all_handlers | Barcha handlerlar | Все обработчики | Every handler
all_error_handlers | Barcha xato handlerlari | Все обработчики ошибок | Every error handler
add | Dekoratorsiz handler qo'shish | Добавить обработчик без декоратора | Add a handler without a decorator

@ref-ui nicebot.keyboards:Button Button
# Tugmalar | Кнопки | Buttons
nicebot.keyboards:Button | Inline tugma | Inline-кнопка | Inline button
nicebot.keyboards:Toggle | Yoqish/o'chirish tugmasi | Кнопка-переключатель | On/off switch
nicebot.keyboards:ReplyButton | Pastki klaviatura tugmasi | Кнопка нижней клавиатуры | Reply keyboard button
nicebot.menu:Menu | Ko'p darajali menyu | Многоуровневое меню | Multi-level menu
nicebot.menu:Menu.add | Menyuga band qo'shish | Добавить пункт | Add an item
nicebot.menu:Menu.item | Funksiyani band qilish | Функция как пункт | A function as an item
# Filtrlar | Фильтры | Filters
nicebot.filters:_F | Tayyor filtrlar F | Готовые фильтры F | Ready-made filters F
nicebot.filters:_F.regex | Regex | Regex | Regex
nicebot.filters:_F.contains | So'z bor | Содержит слово | Contains words
nicebot.filters:_F.user | Foydalanuvchi id | Id пользователя | User ids
nicebot.filters:_F.chat | Chat id | Id чата | Chat ids
nicebot.filters:_F.lang | Til | Язык | Language
nicebot.filters:_F.state | Holat | Состояние | State
nicebot.filters:Filter | O'z filtringiz | Свой фильтр | Your own filter
# Formatlash | Форматирование | Formatting
nicebot.utils:html | Xavfsiz HTML shablon | Безопасный HTML-шаблон | Safe HTML template
nicebot.utils:escape | HTML belgilarni ekranlash | Экранировать HTML | Escape HTML
nicebot.utils:bold | Qalin | Жирный | Bold
nicebot.utils:italic | Kursiv | Курсив | Italic
nicebot.utils:underline | Tagi chizilgan | Подчёркнутый | Underlined
nicebot.utils:strike | Ustidan chizilgan | Зачёркнутый | Strikethrough
nicebot.utils:spoiler | Yashirin matn | Скрытый текст | Spoiler
nicebot.utils:code | Kod | Код | Inline code
nicebot.utils:pre | Kod bloki | Блок кода | Code block
nicebot.utils:link | Havola | Ссылка | Link
nicebot.utils:mention | Foydalanuvchiga havola | Упоминание пользователя | User mention
nicebot.utils:quote | Iqtibos | Цитата | Quote
nicebot.utils:cache | Natijani keshlash | Кэширование результата | Cache a result
nicebot.utils:parse_duration | "1h30m" → soniya | «1h30m» → секунды | "1h30m" → seconds

@ref-media nicebot.media:Media media
# Media | Media | Media
kind | Fayl turi | Тип файла | File kind
file_id | Qayta yuborish uchun id | Id для повторной отправки | Id to send it again
file_unique_id | Barqaror id | Постоянный id | Stable id
size | Hajmi (bayt) | Размер (байт) | Size in bytes
file_size | size bilan bir xil | То же, что size | Same as size
size_text | Hajmi matn ko'rinishida | Размер текстом | Size as text
name | Asl nom | Исходное имя | Original name
filename | Saqlash uchun nom | Имя для сохранения | Name to save under
extension | Kengaytma | Расширение | Extension
mime | MIME turi | MIME-тип | MIME type
width | Kenglik | Ширина | Width
height | Balandlik | Высота | Height
duration | Davomiylik | Длительность | Duration
caption | Izoh | Подпись | Caption
is_image | Rasmmi | Картинка ли | Is it an image
can_download | 20 MB dan kichikmi | Меньше ли 20 МБ | Under 20 MB?
raw | Telegram obyekti | Объект Telegram | The Telegram object
download | Xotiraga yuklab olish | Скачать в память | Download into memory
save | Diskka saqlash | Сохранить на диск | Save to disk
input | Qayta yuborish qiymati | Значение для повторной отправки | Value to send again
of | Xabardan Media yasash | Media из сообщения | Media from a message
# Validatorlar | Валидаторы | Validators
nicebot.validators:Text | Matn | Текст | Text
nicebot.validators:Int | Butun son (Integer) | Целое число (Integer) | Whole number (Integer)
nicebot.validators:Float | Son (Number) | Число (Number) | Number
nicebot.validators:Phone | Telefon | Телефон | Phone
nicebot.validators:Email | Email | Email | Email
nicebot.validators:Url | Havola | Ссылка | Link
nicebot.validators:Date | Sana | Дата | Date
nicebot.validators:Choice | Variantlardan biri | Один из вариантов | One of the options
nicebot.validators:Regex | Regex bo'yicha | По regex | By regex
nicebot.validators:Photo | Rasm | Фото | Photo
nicebot.validators:File | Istalgan fayl | Любой файл | Any file
nicebot.validators:Document | Hujjat | Документ | Document
nicebot.validators:Video | Video | Видео | Video
nicebot.validators:Audio | Musiqa | Музыка | Music
nicebot.validators:Voice | Ovozli xabar | Голосовое | Voice message
nicebot.validators:Location | Joylashuv | Геолокация | Location
nicebot.validators:Custom | O'z funksiyangiz | Своя функция | Your function
nicebot.validators:Validator | O'z validatoringiz | Свой валидатор | Your own validator
# Xatolar | Ошибки | Errors
nicebot.errors:FileTooBig | Fayl 20 MB dan katta | Файл больше 20 МБ | File over 20 MB
nicebot._base:InputFile | Yuklanadigan fayl | Файл для загрузки | A file to upload

@ref-webapp nicebot.server:WebAppRequest req
# WebAppRequest | WebAppRequest | WebAppRequest
user | Tekshirilgan foydalanuvchi | Проверенный пользователь | The verified user
user_id | Telegram id | Telegram id | Telegram id
json | JSON tana | JSON-тело | JSON body
query | URL parametrlari | Параметры URL | URL query
params | Yo'l parametrlari | Параметры пути | Path parameters
init | initData maydonlari | Поля initData | initData fields
start_param | startapp parametri | Параметр startapp | startapp parameter
query_id | answerWebAppQuery uchun id | Id для answerWebAppQuery | Id for answerWebAppQuery
chat_type | Qayerda ochilgan | Где открыто | Where it was opened
headers | HTTP sarlavhalari | HTTP-заголовки | HTTP headers
ip | Mijoz IP manzili | IP клиента | Client IP
request | Xom aiohttp so'rovi | Сырой запрос aiohttp | Raw aiohttp request
bot | Bot | Бот | The bot
db_user | Bazadagi foydalanuvchi | Пользователь в базе | Database user
form | Multipart forma | Multipart-форма | Multipart form
files | Yuklangan fayllar | Загруженные файлы | Uploaded files
send | Foydalanuvchiga xabar | Сообщение пользователю | Message the user
send_photo | Foydalanuvchiga rasm | Фото пользователю | Photo to the user
send_document | Foydalanuvchiga fayl | Файл пользователю | File to the user
answer | Chatga javob (answerWebAppQuery) | Ответ в чат (answerWebAppQuery) | Answer in the chat (answerWebAppQuery)
# Yordamchilar | Помощники | Helpers
nicebot.server:WebAppUser | Mini App foydalanuvchisi | Пользователь Mini App | Mini App user
nicebot.server:UploadedFile | Yuklangan fayl | Загруженный файл | Uploaded file
nicebot.server:validate_init_data | initData'ni tekshirish | Проверить initData | Verify initData
nicebot.server:sign_init_data | initData yaratish (test) | Создать initData (тест) | Build initData (tests)
nicebot.tunnel:Tunnel | HTTPS tunnel | HTTPS-туннель | HTTPS tunnel
nicebot.server:build_app | aiohttp ilovasi | Приложение aiohttp | The aiohttp app
# nicebot.js | nicebot.js | nicebot.js
!nicebot.get(path) | GET so'rov | GET-запрос | GET request
!nicebot.post(path, data) | POST so'rov (JSON) | POST-запрос (JSON) | POST request (JSON)
!nicebot.put(path, data) | PUT so'rov | PUT-запрос | PUT request
!nicebot.del(path) | DELETE so'rov | DELETE-запрос | DELETE request
!nicebot.upload(path, files, fields) | Fayl yuklash | Загрузка файлов | Upload files
!nicebot.mainButton(text, onClick) | Asosiy tugma | Главная кнопка | Main button
!nicebot.hideMainButton() | Asosiy tugmani yashirish | Скрыть главную кнопку | Hide the main button
!nicebot.progress(on) | Tugmada yuklanish | Загрузка на кнопке | Loading on the button
!nicebot.backButton(onClick) | Orqaga tugmasi | Кнопка «Назад» | Back button
!nicebot.alert(text) | Xabar oynasi | Окно сообщения | Message popup
!nicebot.confirm(text) | Ha/Yo'q oynasi | Окно Да/Нет | Yes/No popup
!nicebot.haptic(kind) | Tebranish | Вибрация | Vibration
!nicebot.theme() | Telegram ranglari | Цвета Telegram | Telegram colors
!nicebot.sendData(obj) | Botga ma'lumot yuborish | Отправить данные боту | Send data to the bot
!nicebot.openLink(url) | Havolani ochish | Открыть ссылку | Open a link
!nicebot.openTelegramLink(url) | t.me havolasini ochish | Открыть ссылку t.me | Open a t.me link
!nicebot.share(text, link) | Ulashish | Поделиться | Share
!nicebot.close() | Yopish | Закрыть | Close
!nicebot.storage.get(key) / set(key, value) | Telegram CloudStorage | Telegram CloudStorage | Telegram CloudStorage
!nicebot.user | Foydalanuvchi (faqat ko'rsatish uchun) | Пользователь (только для показа) | User (for display only)
!nicebot.startParam | startapp parametri | Параметр startapp | startapp parameter
!nicebot.isTelegram | Telegram ichidami | Внутри Telegram ли | Inside Telegram?
!nicebot.tg | window.Telegram.WebApp | window.Telegram.WebApp | window.Telegram.WebApp

@ref-testing nicebot.testing:TestSession t
# TestSession | TestSession | TestSession
user | Soxta foydalanuvchi | Тестовый пользователь | Fake user
last | Oxirgi xabar | Последнее сообщение | Last message
last_in | Chatdagi oxirgi xabar | Последнее сообщение в чате | Last message in a chat
last_with_buttons | Tugmali oxirgi xabar | Последнее сообщение с кнопками | Last message with buttons
messages | Barcha xabarlar | Все сообщения | Every message
texts | Barcha matnlar | Все тексты | Every text
answers | Tugma javoblari | Ответы на кнопки | Button answers
calls | Barcha API chaqiruvlari | Все вызовы API | Every API call
calls_of | Bitta metod chaqiruvlari | Вызовы одного метода | Calls of one method
api | Mini App endpointini chaqirish | Вызвать эндпоинт Mini App | Call a Mini App endpoint
files | Yuklab olinadigan fayllar | Файлы для скачивания | Files for downloads
blocked | Botni bloklaganlar | Заблокировавшие бота | Users who blocked the bot
fail_next | Keyingi chaqiruvda xato | Ошибка на следующем вызове | Error on the next call
feed | Xom update | Сырой апдейт | Raw update
settle | Bot tugashini kutish | Дождаться бота | Wait for the bot
reset | Tozalash | Очистить | Reset
# TestUser | TestUser | TestUser
nicebot.testing:TestUser.send | Xabar yuborish | Отправить сообщение | Send a message
nicebot.testing:TestUser.click | Tugmani bosish | Нажать кнопку | Press a button
nicebot.testing:TestUser.send_photo | Rasm yuborish | Отправить фото | Send a photo
nicebot.testing:TestUser.send_document | Hujjat yuborish | Отправить документ | Send a document
nicebot.testing:TestUser.send_video | Video yuborish | Отправить видео | Send a video
nicebot.testing:TestUser.send_voice | Ovozli xabar | Голосовое | Voice message
nicebot.testing:TestUser.send_audio | Musiqa | Музыка | Music
nicebot.testing:TestUser.send_contact | Kontakt | Контакт | Contact
nicebot.testing:TestUser.send_location | Joylashuv | Геолокация | Location
nicebot.testing:TestUser.send_album | Albom | Альбом | Album
nicebot.testing:TestUser.send_web_app_data | Mini App sendData | Mini App sendData | Mini App sendData
nicebot.testing:TestUser.join | Guruhga qo'shilish | Вступить в группу | Join a group
nicebot.testing:TestUser.inline | Inline so'rov | Inline-запрос | Inline query
# SentMessage | SentMessage | SentMessage
nicebot.testing:SentMessage.text | Matn | Текст | Text
nicebot.testing:SentMessage.buttons | Inline tugmalar | Inline-кнопки | Inline buttons
nicebot.testing:SentMessage.keyboard | Pastki klaviatura | Нижняя клавиатура | Reply keyboard
nicebot.testing:SentMessage.media_kind | Fayl turi | Тип файла | File kind
nicebot.testing:SentMessage.chat_id | Chat id | Id чата | Chat id
nicebot.testing:ApiResponse | t.api() javobi | Ответ t.api() | t.api() response
"""

TITLES = {
    "ref-ctx": {"uz": "ctx — to'liq ma'lumotnoma", "ru": "ctx — полный справочник", "en": "ctx — full reference"},
    "ref-bot": {"uz": "Nicebot — to'liq ma'lumotnoma", "ru": "Nicebot — полный справочник", "en": "Nicebot — full reference"},
    "ref-ui": {"uz": "Tugma, menyu, filtr, formatlash", "ru": "Кнопки, меню, фильтры, форматирование", "en": "Buttons, menus, filters, formatting"},
    "ref-media": {"uz": "Media va validatorlar", "ru": "Media и валидаторы", "en": "Media and validators"},
    "ref-webapp": {"uz": "Mini App: req va nicebot.js", "ru": "Mini App: req и nicebot.js", "en": "Mini App: req and nicebot.js"},
    "ref-testing": {"uz": "Test vositalari", "ru": "Инструменты тестов", "en": "Testing tools"},
}

INTRO = {
    "ref-ctx": {
        "uz": "Har bir handler oladigan `ctx` obyektining barcha xususiyat va metodlari. Imzo va misollar kutubxonaning o'zidan olingan — VS Code'da sichqonchani metod ustiga olib borsangiz ham xuddi shu misolni ko'rasiz.",
        "ru": "Все свойства и методы объекта `ctx`, который получает каждый обработчик. Сигнатуры и примеры взяты из самой библиотеки — тот же пример вы увидите в VS Code, наведя мышь на метод.",
        "en": "Every property and method of the `ctx` object each handler receives. Signatures and examples come from the library itself — you see the same example when you hover a method in VS Code.",
    },
    "ref-bot": {
        "uz": "`Nicebot` obyektining metodlari: ishga tushirish, handler dekoratorlari, Mini App, fayllar va biznes vositalari. Bundan tashqari Bot API'ning 185 ta metodi ham `bot` da bor — [Bot API](#api) sahifasiga qarang.",
        "ru": "Методы объекта `Nicebot`: запуск, декораторы обработчиков, Mini App, файлы и бизнес-инструменты. Кроме того, у `bot` есть все 185 методов Bot API — см. [Bot API](#api).",
        "en": "Methods of the `Nicebot` object: running, handler decorators, Mini Apps, files and business tools. On top of that `bot` has all 185 Bot API methods — see [Bot API](#api).",
    },
    "ref-ui": {
        "uz": "Tugmalar, klaviaturalar, menyular, filtrlar va matn formatlash yordamchilari.",
        "ru": "Кнопки, клавиатуры, меню, фильтры и помощники форматирования текста.",
        "en": "Buttons, keyboards, menus, filters and text formatting helpers.",
    },
    "ref-media": {
        "uz": "`ctx.media` qaytaradigan `Media` obyekti va `ctx.ask` uchun barcha validatorlar.",
        "ru": "Объект `Media`, который возвращает `ctx.media`, и все валидаторы для `ctx.ask`.",
        "en": "The `Media` object returned by `ctx.media`, and every validator for `ctx.ask`.",
    },
    "ref-webapp": {
        "uz": "`@bot.api` handlerlari oladigan `req` obyekti, yordamchi klasslar va brauzerdagi `nicebot.js` funksiyalari.",
        "ru": "Объект `req` в обработчиках `@bot.api`, вспомогательные классы и функции `nicebot.js` в браузере.",
        "en": "The `req` object of `@bot.api` handlers, helper classes and the browser-side `nicebot.js` functions.",
    },
    "ref-testing": {
        "uz": "`async with bot.test() as t:` ichida ishlatiladigan obyektlar.",
        "ru": "Объекты, которые используются внутри `async with bot.test() as t:`.",
        "en": "Objects you use inside `async with bot.test() as t:`.",
    },
}

DESC = {
    "ref-ctx": {"uz": "ctx'ning barcha xususiyat va metodlari: imzo, tavsif va misol.", "ru": "Все свойства и методы ctx: сигнатура, описание и пример.", "en": "Every property and method of ctx: signature, description and example."},
    "ref-bot": {"uz": "Nicebot metodlari va handler dekoratorlari.", "ru": "Методы Nicebot и декораторы обработчиков.", "en": "Nicebot methods and handler decorators."},
    "ref-ui": {"uz": "Button, Toggle, Menu, F filtrlari va formatlash.", "ru": "Button, Toggle, Menu, фильтры F и форматирование.", "en": "Button, Toggle, Menu, F filters and formatting."},
    "ref-media": {"uz": "Media obyekti va barcha validatorlar.", "ru": "Объект Media и все валидаторы.", "en": "The Media object and every validator."},
    "ref-webapp": {"uz": "WebAppRequest, yordamchilar va nicebot.js.", "ru": "WebAppRequest, помощники и nicebot.js.", "en": "WebAppRequest, helpers and nicebot.js."},
    "ref-testing": {"uz": "TestSession, TestUser va SentMessage.", "ru": "TestSession, TestUser и SentMessage.", "en": "TestSession, TestUser and SentMessage."},
}


def parse() -> dict:
    """Parse SPEC into {page: {"target", "prefix", "groups": [(titles, [(member, {lang: text}, raw)])]}}."""
    pages: dict = {}
    cur = None
    for line in SPEC.strip().splitlines():
        line = line.rstrip()
        if not line:
            continue
        if line.startswith("@"):
            pid, target, prefix = line[1:].split()
            cur = pages[pid] = {"target": target, "prefix": prefix, "groups": []}
        elif line.startswith("# "):
            uz, ru, en = [x.strip() for x in line[2:].split("|")]
            cur["groups"].append(({"uz": uz, "ru": ru, "en": en}, []))
        else:
            raw = line.startswith("!")
            name, uz, ru, en = [x.strip() for x in line.lstrip("!").split("|")]
            cur["groups"][-1][1].append((name, {"uz": uz, "ru": ru, "en": en}, raw))
    return pages
