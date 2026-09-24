# برنامه بازطراحی رابط کاربری Telegram Harbor

## هدف

این سند برای بازطراحی بصری Telegram Harbor روی شاخه `gui` تهیه شده است.

هدف، تغییر رفتار محصول نیست. قابلیت‌های فعلی باید حفظ شوند و تمرکز این مرحله روی موارد زیر است:

- خوانایی بهتر؛
- سلسله‌مراتب بصری روشن؛
- کاهش شلوغی صفحه؛
- یکپارچگی رنگ، فاصله، border، radius و typography؛
- تفکیک واضح navigation، filter، action و content؛
- بهبود تجربه دسکتاپ و صفحه‌های کوچک؛
- حفظ سازگاری با Streamlit و جلوگیری از CSS شکننده.

---

## ارزیابی وضعیت فعلی

رابط فعلی از نظر عملکردی کامل و قابل استفاده است، اما از نظر بصری هنوز بیشتر شبیه یک پنل Streamlit توسعه‌دهنده است تا یک محصول نهایی.

### نقاط مثبت فعلی

- بخش پیام‌ها scroll مستقل دارد و header دیگر با پیام‌ها overlap نمی‌کند.
- کنترل‌های Chat / Search / Tag / Date Range در یک ناحیه مشخص جمع شده‌اند.
- Refresh Messages و Load More Messages در خارج از scroll پیام قرار دارند.
- Sidebar به‌صورت منطقی شامل Web Account، Network و Telegram Accounts است.
- پیام‌ها در card جداگانه نمایش داده می‌شوند.
- stateهای مهم مانند اتصال Telegram، خطا، دانلود و حذف دارای feedback هستند.

### مسائل بصری اصلی

1. **همه کنترل‌ها تقریباً وزن بصری یکسان دارند.**
   دکمه‌های حیاتی، secondary و destructive تفاوت کافی ندارند.

2. **صفحه hierarchy کافی ندارد.**
   کاربر باید با نگاه کردن و خواندن labelها بفهمد کدام قسمت navigation است، کدام filter و کدام action.

3. **Sidebar از نظر اطلاعاتی متراکم است.**
   Account، Proxy، Telegram Account و actionهای مختلف پشت سر هم دیده می‌شوند و grouping بصری محدودی دارند.

4. **Message Card هنوز شکل یک فرم دارد.**
   Tag input، Save و Delete در سمت راست card باعث می‌شود محتوای پیام با ابزار مدیریت پیام رقابت کند.

5. **فضای سفید و rhythm یکنواخت نیست.**
   فاصله بین panelها، buttonها، captionها و cardها عمدتاً بر اساس defaults خود Streamlit است.

6. **استفاده زیاد از emoji نقش icon system را بازی می‌کند.**
   این روش ساده است ولی در اندازه، baseline و style یکنواخت نیست.

7. **رنگ معنایی محدود است.**
   Connected، Warning، Delete، Download، Refresh و Navigation بهتر است hierarchy رنگی مشخصی داشته باشند.

8. **Login/Create Account صفحه‌ای کاربردی اما بدون هویت بصری قوی است.**
   برند Telegram Harbor در آن حضور دارد، ولی landing/auth experience هنوز ساده است.

9. **Responsive behavior طراحی‌شده نیست؛ بیشتر سازگار شده است.**
   باید breakpointها و stacking رفتار کنترل‌ها صریح طراحی شوند.

---

# جهت طراحی پیشنهادی

## شخصیت بصری

پیشنهاد: **Clean Utility / Harbor Console**

ویژگی‌ها:

- حرفه‌ای و کم‌حاشیه؛
- مناسب استفاده طولانی‌مدت؛
- تمرکز روی محتوا، نه decoration؛
- الهام از ابزارهای مدرن مدیریت پیام و عملیات؛
- هویت بصری دریایی Telegram Harbor به‌صورت subtle، نه theme نمایشی.

از gradientهای زیاد، shadowهای سنگین و animationهای تزئینی باید پرهیز شود.

---

# Design Tokens

در مرحله پیاده‌سازی بهتر است styleها به token تبدیل شوند تا CSS پراکنده نشود.

## رنگ‌ها

به‌جای hard-code کردن رنگ در هر widget، متغیرهای معنایی تعریف شوند:

- `--th-bg`: background اصلی
- `--th-surface`: سطح panel/card
- `--th-surface-raised`: سطح برجسته
- `--th-border`: border عمومی
- `--th-text`: متن اصلی
- `--th-text-muted`: caption/meta
- `--th-accent`: رنگ اصلی Telegram Harbor
- `--th-accent-soft`: پس‌زمینه accent
- `--th-success`: connected/success
- `--th-warning`: warning/fallback/cache state
- `--th-danger`: delete/destructive
- `--th-info`: media/download/information

هدف این است که dark/light mode هر دو قابل پشتیبانی باشند.

## Radius

پیشنهاد:

- control: 8px
- panel: 12px
- message card: 12px
- badge/chip: 999px

نباید هر بخش radius متفاوت داشته باشد.

## فاصله

یک scale محدود:

- 4px
- 8px
- 12px
- 16px
- 24px
- 32px

این scale باید جای margin/paddingهای تصادفی را بگیرد.

## Typography

سه سطح اصلی کافی است:

- Page/Product title
- Section title
- Body / Meta

Metadata مثل date، ID، file size و MIME باید کوچک‌تر و کم‌رنگ‌تر از متن پیام باشد.

---

# ساختار صفحه پیشنهادی

## 1. Sidebar

Sidebar باید از حالت «فرم تنظیمات طولانی» به «navigation/status rail» نزدیک شود.

### بخش Brand

بالا:

- آیکون Anchor
- Telegram Harbor
- version کوچک

Tagline دائمی ضروری نیست و می‌تواند حذف یا بسیار کم‌رنگ شود.

### بخش Web Account

به‌جای چند خط متن:

- Avatar placeholder دایره‌ای
- Display Name
- @username
- Logout به‌عنوان action کم‌وزن

### بخش Telegram Account

Active Telegram Account باید مهم‌ترین کنترل Sidebar باشد.

پیشنهاد:

- label کوچک: Telegram account
- account selector
- status chip: Connected / Disconnected
- Refresh Chats به شکل icon/action کوچک
- Add Account به عنوان secondary action
- Disconnect و Logout Telegram در یک menu/expander با عنوان Account actions

این کار خطر کلیک اشتباه روی Logout را نیز کم می‌کند.

### بخش Network

Proxy تنظیم روزمره نیست؛ بهتر است داخل expander باشد:

`Network & Proxy`

در حالت بسته فقط status نشان داده شود:

- Proxy On
- Proxy Off

در نتیجه Sidebar بسیار خلوت‌تر می‌شود.

---

# 2. Main Header / Filter Panel

پنل فعلی باید به یک toolbar واقعی تبدیل شود.

## ردیف اول

- Chat selector: بیشترین عرض
- Search: عرض متوسط
- Tag filter: عرض کوچک

## ردیف دوم

- Date range
- Previous Day
- Next Day
- Clear filters در صورت فعال بودن search/tag غیرپیش‌فرض

### بهبود hierarchy

labelهای بزرگ و emojiدار فعلی می‌توانند سبک‌تر شوند.

مثلاً:

- Chat
- Search messages
- Tag
- Date range

icon در داخل control یا prefix بهتر از emoji در labelهای بلند است.

### Active Filter Summary

در صورت فعال بودن search/tag/date خاص، یک row کوچک chip نمایش داده شود:

`Search: invoice`  `Tag: work`  `7 days`

این بخش optional است و باید بعد از baseline styling اجرا شود.

---

# 3. Action Bar

Refresh Messages و Load More Messages اکنون در جای درستی قرار گرفته‌اند، اما visual hierarchy بهتر می‌شود:

- Refresh Messages: secondary/outline
- Load More Messages: primary فقط وقتی قابل استفاده است
- count/status در سمت مقابل

پیشنهاد desktop:

`[Refresh] [Load more]                         37 visible · 100 loaded`

به این ترتیب caption داخل scroll panel حذف یا بسیار ساده می‌شود و فضای پیام بیشتر می‌شود.

---

# 4. Message List

این مهم‌ترین بخش محصول است.

## ساختار پیشنهادی Message Card

به‌جای دو ستون ثابت `4:1`، card سه ناحیه داشته باشد:

### Header card

- timestamp
- message ID در صورت نیاز
- type/media badge
- overflow actions

### Body

- متن یا caption
- media preview/playback
- metadata فایل

### Footer

- tag chips
- Edit tags
- Delete در overflow/action group

### دلیل

در UI فعلی Tag textbox و Delete دائماً در سمت راست هر پیام دیده می‌شوند و توجه زیادی می‌گیرند، حتی وقتی کاربر فقط در حال خواندن پیام است.

پیشنهاد این است:

- tags در حالت عادی به شکل chip نمایش داده شوند؛
- `Edit tags` فقط هنگام نیاز input را باز کند؛
- Delete پشت action menu یا confirmation action کم‌وزن باشد.

این تغییر بیشترین اثر را در حرفه‌ای شدن ظاهر صفحه دارد.

---

# 5. Tag Design

Tagها بهتر است از comma-separated text به نمایش بصری chip تبدیل شوند، بدون تغییر مدل داده.

حالت خواندن:

`work` `important` `customer`

حالت edit:

- input فعلی باز شود؛
- Save/Cancel کنار هم؛
- chipها بعد از save refresh شوند.

رنگ tagها در فاز اول بهتر است neutral باشد؛ رنگ‌بندی per-tag می‌تواند feature آینده باشد.

---

# 6. Media Experience

## Photo

قبل از Load:

- یک placeholder کوچک با icon و metadata
- button: Preview

بعد از Load:

- تصویر با max width مناسب card
- border-radius هماهنگ

## Video

قبل از Load:

- media panel با نوع، size، duration و MIME
- Play/Load به‌عنوان primary media action

بعد از Load:

- video
- Download
- Redownload در secondary/danger-low-priority style

نباید سه button بزرگ با وزن یکسان زیر video قرار بگیرند.

---

# 7. Status و Feedback

## Telegram connection

به‌جای متن سبز بزرگ:

`● Connected`

یک status chip compact کافی است.

## Cached Chats

چون dialog cache اضافه شده است، می‌توان بعداً source را نشان داد:

- Cached
- Refreshed just now

ولی این اطلاعات نباید در UI اصلی شلوغی ایجاد کند.

## Loading

برای عملیات طولانی:

- skeleton یا status line در صورت امکان؛
- spinner فقط برای عملیات کوتاه؛
- progress واقعی برای media حفظ شود.

---

# 8. Auth Screen

Login/Create Account می‌تواند بسیار حرفه‌ای‌تر شود.

پیشنهاد desktop:

یک card مرکزی با max-width حدود 420–480px:

- Anchor mark
- Telegram Harbor
- متن کوتاه
- Login/Create Account tabs
- فرم
- footer کوچک با version

در نمایش بزرگ می‌توان یک panel معرفی سمت چپ داشت، ولی برای scope فعلی card مرکزی بهتر و کم‌ریسک‌تر است.

---

# 9. Empty States

برای وضعیت‌های زیر طراحی dedicated لازم است:

- هنوز Telegram account اضافه نشده
- Telegram disconnected
- chat list خالی
- هیچ پیام در range نیست
- search نتیجه ندارد
- media unavailable

Empty state باید شامل:

- icon
- عنوان کوتاه
- توضیح یک خطی
- action واضح در صورت وجود

نه فقط `st.info()`.

---

# 10. Responsive Design

## Desktop بزرگ

- Sidebar ثابت
- toolbar دو ردیف
- message card با max-width منطقی
- action bar افقی

## Laptop

- عرض ستون Tag و Search کنترل شود
- هیچ control از viewport بیرون نزند

## Tablet / صفحه باریک

- toolbar به چند ردیف stack شود
- Chat selector تمام عرض
- Search + Tag زیر آن
- Date + navigation ردیف جدا
- action bar wrap شود
- message management column به footer card منتقل شود

## Mobile

Streamlit محدودیت دارد، بنابراین هدف mobile-perfect نیست؛ هدف usable و بدون overlap است.

---

# 11. Accessibility

در طراحی جدید باید رعایت شود:

- contrast مناسب متن/پس‌زمینه؛
- فقط از رنگ برای انتقال مفهوم استفاده نشود؛
- Delete همیشه متن/علامت واضح داشته باشد؛
- focus state برای input/button حذف نشود؛
- اندازه hit target دکمه‌ها حداقل حدود 40px؛
- metadata بیش از حد کم‌رنگ نشود؛
- disabled state واضح باشد.

---

# 12. مواردی که نباید در فاز GUI تغییر کنند

برای کاهش regression:

- business logic Telegram؛
- SQLite schema مگر واقعاً برای UI لازم شود؛
- tag identity؛
- media cache semantics؛
- Remember Me behavior؛
- Telegram runtime؛
- dialog cache؛
- message pagination semantics؛
- encryption/session logic.

GUI branch باید تا حد ممکن presentation-only باقی بماند.

---

# برنامه اجرایی پیشنهادی

## GUI-P0 — Design Foundation

هدف: ساخت زیرساخت ظاهری بدون تغییر layout اصلی.

- [ ] ایجاد یک فایل مرکزی style/theme برای Telegram Harbor.
- [ ] تعریف design tokens برای color، spacing، radius، border، shadow و text.
- [ ] حذف CSS پراکنده از `ui/main.py` و انتقال به style layer.
- [ ] ایجاد helperهای reusable برای badge/status/chip/section title در حدی که Streamlit اجازه می‌دهد.
- [ ] تست light/dark mode.
- [ ] regression test برای class/keyهای CSS حساس.

معیار پذیرش:
- ظاهر فعلی نباید خراب شود.
- همه styleهای اصلی یک منبع مرکزی داشته باشند.

---

## GUI-P1 — Sidebar Redesign

- [ ] Brand header compact.
- [ ] Web account card.
- [ ] Telegram account selector + connection badge.
- [ ] انتقال Disconnect/Logout Telegram به بخش Account actions.
- [ ] Proxy settings در expander.
- [ ] hierarchy واضح برای Add Account و Refresh Chats.
- [ ] spacing و dividerهای یکپارچه.

معیار پذیرش:
- Sidebar در یک نگاه قابل فهم باشد.
- actionهای destructive با actionهای روزمره اشتباه نشوند.

---

## GUI-P2 — Main Toolbar

- [ ] بازطراحی filter panel.
- [ ] Chat selector به‌عنوان control اصلی.
- [ ] Search و Tag سبک‌تر.
- [ ] Date navigation compact.
- [ ] action bar یکپارچه با Refresh/Load More و message counts.
- [ ] بررسی optional filter chips.

معیار پذیرش:
- toolbar کمتر از محتوای پیام توجه بگیرد.
- controlها در desktop/laptop بدون clipping باشند.

---

## GUI-P3 — Message Card Redesign

بالاترین اولویت بصری.

- [ ] card header با timestamp/media type.
- [ ] body با typography خواناتر.
- [ ] metadata secondary.
- [ ] tagها به شکل chip در حالت read.
- [ ] Edit Tags به صورت on-demand.
- [ ] Delete از حالت button دائمی بزرگ خارج شود.
- [ ] media actions hierarchy.
- [ ] spacing ثابت بین cards.

معیار پذیرش:
- یک صفحه با 10 پیام باید visually calm باشد.
- متن پیام مهم‌ترین عنصر card باشد.
- مدیریت tag/delete فقط هنگام نیاز برجسته شود.

---

## GUI-P4 — Auth + Empty/Loading/Error States

- [ ] login card مرکزی.
- [ ] branding و version.
- [ ] empty state برای Telegram account.
- [ ] empty state برای no messages/no search result.
- [ ] error/warning style یکپارچه.
- [ ] loading states هماهنگ.

---

## GUI-P5 — Responsive + Accessibility

- [ ] breakpoint desktop/laptop/tablet.
- [ ] کنترل wrapping toolbar.
- [ ] message card mobile stacking.
- [ ] contrast review.
- [ ] keyboard/focus review.
- [ ] destructive action review.
- [ ] manual screenshots در حداقل سه viewport.

---

## GUI-P6 — Polish

فقط بعد از تثبیت مراحل قبل:

- [ ] subtle hover states.
- [ ] transitionهای کوتاه و محدود.
- [ ] active/selected chat state واضح‌تر.
- [ ] icon consistency.
- [ ] microcopy cleanup.
- [ ] بررسی حذف emojiهایی که نقش icon system دارند.

---

# اولویت پیشنهادی

ترتیب اجرایی پیشنهادی:

1. GUI-P0 — Design tokens/style foundation
2. GUI-P3 — Message cards
3. GUI-P1 — Sidebar
4. GUI-P2 — Main toolbar/action bar
5. GUI-P4 — Auth/empty states
6. GUI-P5 — Responsive/accessibility
7. GUI-P6 — Polish

دلیل قرار گرفتن Message Card قبل از Sidebar این است که بیشترین زمان کاربر داخل message list می‌گذرد و بزرگ‌ترین اثر ظاهری از آنجا حاصل می‌شود.

---

# پیشنهاد اجرایی

برای کاهش ریسک، هر فاز باید commit مستقل داشته باشد و قبل از رفتن به فاز بعد:

1. CI سبز باشد.
2. screenshot desktop بررسی شود.
3. behavior فعلی پیام‌ها، tags، media، delete و pagination دست‌نخورده بماند.
4. در صورت تغییر CSS مربوط به Streamlit DOM، regression test اضافه شود.

بهتر است اولین implementation روی `gui` فقط **GUI-P0** باشد و بعد از مشاهده screenshot و تأیید بصری، سراغ Message Card برویم.
