"""Bot messages in Persian, English, French and German."""

LANGS = {"fa": "فارسی 🇮🇷", "en": "English 🇬🇧", "fr": "Français 🇫🇷", "de": "Deutsch 🇩🇪"}

T = {
    "choose_lang": {
        "fa": "زبان ربات رو انتخاب کن:",
        "en": "Choose the bot's language:",
        "fr": "Choisis la langue du bot :",
        "de": "Wähle die Sprache des Bots:",
    },
    "lang_set": {
        "fa": "زبان: فارسی ✅",
        "en": "Language: English ✅",
        "fr": "Langue : français ✅",
        "de": "Sprache: Deutsch ✅",
    },
    "welcome": {
        "fa": "سلام! 👋 من آگهی‌های جدید Anibis، tutti و Ricardo رو برات پیدا می‌کنم: وسایل رایگان در منطقه‌ات و هر چیزی که بخوای.\n\n"
              "اول بگو کجا زندگی می‌کنی؟ اسم شهر یا کانتون رو بنویس (مثلاً Lausanne یا Vaud).",
        "en": "Hi! 👋 I find new Anibis, tutti and Ricardo listings for you: free items in your area and anything you're looking for.\n\n"
              "First, where do you live? Type a town or canton (e.g. Lausanne or Vaud).",
        "fr": "Salut ! 👋 Je trouve pour toi les nouvelles annonces Anibis, tutti et Ricardo : objets gratuits près de chez toi et tout ce que tu cherches.\n\n"
              "D'abord, où habites-tu ? Écris une ville ou un canton (p. ex. Lausanne ou Vaud).",
        "de": "Hallo! 👋 Ich finde neue Inserate auf Anibis, tutti und Ricardo für dich: Gratis-Sachen in deiner Nähe und alles, was du suchst.\n\n"
              "Wo wohnst du? Schreib einen Ort oder Kanton (z. B. Lausanne oder Waadt).",
    },
    "ask_region": {
        "fa": "اسم شهر یا کانتونت رو بنویس (مثلاً Lausanne یا Vaud).",
        "en": "Type your town or canton (e.g. Lausanne or Vaud).",
        "fr": "Écris ta ville ou ton canton (p. ex. Lausanne ou Vaud).",
        "de": "Schreib deinen Ort oder Kanton (z. B. Lausanne oder Waadt).",
    },
    "searching_loc": {
        "fa": "دارم در Anibis دنبال «{q}» می‌گردم…",
        "en": "Looking up “{q}” on Anibis…",
        "fr": "Je cherche « {q} » sur Anibis…",
        "de": "Ich suche „{q}“ auf Anibis…",
    },
    "loc_not_found": {
        "fa": "«{q}» رو در Anibis پیدا نکردم 😕 اسم شهر رو همون‌طور که روی Anibis نوشته می‌شه بنویس (مثلاً Lausanne، Geneve، Zurich، Biel) یا اسم کانتون.",
        "en": "I couldn't find “{q}” on Anibis 😕 Write the town as Anibis spells it (e.g. Lausanne, Geneve, Zurich, Biel) or a canton name.",
        "fr": "Je n'ai pas trouvé « {q} » sur Anibis 😕 Écris la ville comme sur Anibis (p. ex. Lausanne, Geneve, Zurich, Biel) ou un canton.",
        "de": "„{q}“ habe ich auf Anibis nicht gefunden 😕 Schreib den Ort wie auf Anibis (z. B. Lausanne, Geneve, Zurich, Biel) oder einen Kanton.",
    },
    "loc_choose": {
        "fa": "این گزینه‌ها در Anibis پیدا شد. کدوم مد نظرته؟",
        "en": "These options exist on Anibis. Which one do you mean?",
        "fr": "Voici les options trouvées sur Anibis. Laquelle veux-tu ?",
        "de": "Diese Optionen gibt es auf Anibis. Welche meinst du?",
    },
    "opt_city": {"fa": "📍 فقط {name}", "en": "📍 {name} (town only)", "fr": "📍 {name} (ville seulement)", "de": "📍 nur {name} (Ort)"},
    "opt_radius": {"fa": "⭕ {name} + {km} کیلومتر", "en": "⭕ {name} + {km} km", "fr": "⭕ {name} + {km} km", "de": "⭕ {name} + {km} km"},
    "opt_region": {"fa": "🗺 منطقه‌ی {name}", "en": "🗺 {name} region", "fr": "🗺 Région {name}", "de": "🗺 Region {name}"},
    "opt_canton": {"fa": "🏔 کانتون {name}", "en": "🏔 Canton {name}", "fr": "🏔 Canton {name}", "de": "🏔 Kanton {name}"},
    "opt_other": {"fa": "✏️ یه جای دیگه", "en": "✏️ Somewhere else", "fr": "✏️ Un autre endroit", "de": "✏️ Anderer Ort"},
    "listings_count": {"fa": "{n} آگهی", "en": "{n} listings", "fr": "{n} annonces", "de": "{n} Inserate"},
    "region_saved": {
        "fa": "✅ منطقه: <b>{label}</b>\n⏳ دارم Anibis، tutti و Ricardo رو بررسی می‌کنم، گزارشش الان میاد.\n\nهر {hours} ساعت آگهی‌های جدید رو می‌فرستم.\n"
              "🎁 آگهی‌های رایگان: {free}\n➕ برای اضافه کردن چیزی که می‌خوای، فقط اسمش رو بفرست (به هر زبانی) یا /add\nℹ️ راهنما: /help",
        "en": "✅ Area: <b>{label}</b>\n⏳ Checking Anibis, tutti and Ricardo now, a report follows.\n\nI'll send new listings every {hours} hours.\n"
              "🎁 Free items: {free}\n➕ To add something you want, just send its name (any language) or use /add\nℹ️ Help: /help",
        "fr": "✅ Zone : <b>{label}</b>\n⏳ Je vérifie Anibis, tutti et Ricardo, un rapport suit.\n\nJ'enverrai les nouvelles annonces toutes les {hours} heures.\n"
              "🎁 Objets gratuits : {free}\n➕ Pour ajouter ce que tu cherches, envoie simplement son nom (n'importe quelle langue) ou /add\nℹ️ Aide : /help",
        "de": "✅ Gebiet: <b>{label}</b>\n⏳ Ich prüfe jetzt Anibis, tutti und Ricardo, ein Bericht folgt.\n\nIch schicke dir alle {hours} Stunden neue Inserate.\n"
              "🎁 Gratis-Sachen: {free}\n➕ Um etwas hinzuzufügen, schick einfach den Namen (jede Sprache) oder /add\nℹ️ Hilfe: /help",
    },
    "help": {
        "fa": "دستورها:\n/add &lt;چیز&gt; – اضافه کردن چیزی که می‌خوای (مثلاً /add دوچرخه)\n/list – لیست و تنظیمات (حذف با دکمه)\n"
              "/free – روشن/خاموش کردن آگهی‌های رایگان\n/check – همین الان بگرد\n/region – عوض کردن منطقه\n/language – عوض کردن زبان\n/sites – انتخاب سایت‌ها (Anibis، tutti، Ricardo)\n/price – تعیین یا تغییر حداقل و حداکثر قیمت\n/stop – توقف همه‌ی هشدارها\n\n"
              "می‌تونی فقط اسم چیزی که می‌خوای رو بفرستی؛ خودم به آلمانی، فرانسوی، ایتالیایی و انگلیسی ترجمه‌اش می‌کنم و در Anibis، tutti و Ricardo می‌گردم.",
        "en": "Commands:\n/add &lt;item&gt; – watch for something (e.g. /add bike)\n/list – your list and settings (remove with buttons)\n"
              "/free – free-item alerts on/off\n/check – search now\n/region – change area\n/language – change language\n/sites – choose sites (Anibis, tutti, Ricardo)\n/price – set or change min and max price\n/stop – stop all alerts\n\n"
              "You can also just send the name of what you want. I translate it to German, French, Italian and English and search Anibis, tutti and Ricardo for all of them.",
        "fr": "Commandes :\n/add &lt;objet&gt; – surveiller un objet (p. ex. /add vélo)\n/list – ta liste et tes réglages (supprimer avec les boutons)\n"
              "/free – alertes objets gratuits on/off\n/check – chercher maintenant\n/region – changer de zone\n/language – changer de langue\n/sites – choisir les sites (Anibis, tutti, Ricardo)\n/price – prix minimum et maximum\n/stop – arrêter toutes les alertes\n\n"
              "Tu peux aussi envoyer juste le nom de ce que tu cherches. Je le traduis en allemand, français, italien et anglais et je cherche sur Anibis, tutti et Ricardo.",
        "de": "Befehle:\n/add &lt;Sache&gt; – nach etwas suchen (z. B. /add Velo)\n/list – deine Liste und Einstellungen (mit Knöpfen löschen)\n"
              "/free – Gratis-Alarme ein/aus\n/check – jetzt suchen\n/region – Gebiet ändern\n/language – Sprache ändern\n/sites – Seiten wählen (Anibis, tutti, Ricardo)\n/price – Mindest- und Höchstpreis\n/stop – alle Alarme stoppen\n\n"
              "Du kannst auch einfach den Namen schicken. Ich übersetze ihn auf Deutsch, Französisch, Italienisch und Englisch und suche auf Anibis, tutti und Ricardo.",
    },
    "need_region": {
        "fa": "اول منطقه‌ات رو مشخص کن: /region",
        "en": "Set your area first: /region",
        "fr": "Choisis d'abord ta zone : /region",
        "de": "Leg zuerst dein Gebiet fest: /region",
    },
    "add_usage": {
        "fa": "بعد از /add بنویس چی می‌خوای، مثلاً: /add دوچرخه",
        "en": "Write what you want after /add, e.g. /add bike",
        "fr": "Écris ce que tu cherches après /add, p. ex. /add vélo",
        "de": "Schreib nach /add, was du suchst, z. B. /add Velo",
    },
    "translating": {
        "fa": "دارم «{kw}» رو ترجمه می‌کنم…",
        "en": "Translating “{kw}”…",
        "fr": "Je traduis « {kw} »…",
        "de": "Ich übersetze „{kw}“…",
    },
    "confirm_terms": {
        "fa": "«{kw}» رو با این کلمه‌ها در هر سه سایت می‌گردم:\n<b>{terms}</b>\n\nاضافه کنم؟",
        "en": "I'll search all three sites for “{kw}” with these words:\n<b>{terms}</b>\n\nAdd it?",
        "fr": "Je chercherai « {kw} » sur les trois sites avec ces mots :\n<b>{terms}</b>\n\nJe l'ajoute ?",
        "de": "Ich suche „{kw}“ auf allen drei Seiten mit diesen Wörtern:\n<b>{terms}</b>\n\nHinzufügen?",
    },
    "added": {
        "fa": "✅ «{kw}» اضافه شد. ⏳ الان همه‌ی آگهی‌های فعلیش در {label} رو از هر سه سایت می‌فرستم، بعد هر {hours} ساعت آگهی‌های جدید.",
        "en": "✅ Added “{kw}”. ⏳ Sending everything listed now in {label} on all three sites, then new listings every {hours} hours.",
        "fr": "✅ « {kw} » ajouté. ⏳ J'envoie tout ce qui est en ligne à {label} sur les trois sites, puis les nouvelles annonces toutes les {hours} heures.",
        "de": "✅ „{kw}“ hinzugefügt. ⏳ Ich schicke alles, was jetzt in {label} auf allen drei Seiten ist, danach alle {hours} Stunden neue Inserate.",
    },
    "already": {
        "fa": "«{kw}» از قبل توی لیسته.", "en": "“{kw}” is already on your list.",
        "fr": "« {kw} » est déjà dans ta liste.", "de": "„{kw}“ ist schon auf deiner Liste.",
    },
    "too_many": {
        "fa": "حداکثر {n} مورد می‌تونی داشته باشی. اول یکی رو از /list حذف کن.",
        "en": "You can have at most {n} items. Remove one in /list first.",
        "fr": "Tu peux avoir au maximum {n} objets. Supprimes-en un dans /list d'abord.",
        "de": "Du kannst höchstens {n} Sachen haben. Lösch zuerst eine in /list.",
    },
    "removed": {
        "fa": "🗑 «{kw}» حذف شد.", "en": "🗑 Removed “{kw}”.",
        "fr": "🗑 « {kw} » supprimé.", "de": "🗑 „{kw}“ gelöscht.",
    },
    "cancelled": {"fa": "باشه.", "en": "OK.", "fr": "D'accord.", "de": "Okay."},
    "list": {
        "fa": "📍 منطقه: <b>{label}</b>\n🎁 آگهی‌های رایگان: {free}\n🔎 چیزهایی که می‌خوای:\n{items}\n\n🕒 آخرین بررسی: {last}\n\n💰 تغییر بازه‌ی قیمت · 🗑 حذف",
        "en": "📍 Area: <b>{label}</b>\n🎁 Free items: {free}\n🔎 You're looking for:\n{items}\n\n🕒 Last check: {last}\n\n💰 change price range · 🗑 remove",
        "fr": "📍 Zone : <b>{label}</b>\n🎁 Objets gratuits : {free}\n🔎 Tu cherches :\n{items}\n\n🕒 Dernière recherche : {last}\n\n💰 changer la fourchette de prix · 🗑 supprimer",
        "de": "📍 Gebiet: <b>{label}</b>\n🎁 Gratis-Sachen: {free}\n🔎 Du suchst:\n{items}\n\n🕒 Letzte Suche: {last}\n\n💰 Preisspanne ändern · 🗑 löschen",
    },
    "list_empty": {
        "fa": "  (هیچی – فقط اسم چیزی که می‌خوای رو بفرست)", "en": "  (nothing yet – just send the name of what you want)",
        "fr": "  (rien – envoie le nom de ce que tu cherches)", "de": "  (noch nichts – schick einfach den Namen)",
    },
    "on": {"fa": "روشن ✅", "en": "on ✅", "fr": "activé ✅", "de": "an ✅"},
    "off": {"fa": "خاموش ❌", "en": "off ❌", "fr": "désactivé ❌", "de": "aus ❌"},
    "free_toggled": {
        "fa": "🎁 آگهی‌های رایگان: {state}", "en": "🎁 Free items: {state}",
        "fr": "🎁 Objets gratuits : {state}", "de": "🎁 Gratis-Sachen: {state}",
    },
    "checking": {"fa": "🔎 دارم می‌گردم…", "en": "🔎 Searching…", "fr": "🔎 Je cherche…", "de": "🔎 Ich suche…"},
    "check_done": {
        "fa": "بررسی تموم شد: {n} آگهی جدید.", "en": "Done: {n} new listings.",
        "fr": "Terminé : {n} nouvelles annonces.", "de": "Fertig: {n} neue Inserate.",
    },
    "first_check": {
        "fa": "برای «{what}» {n} آگهی فعلی رو یادم موند. از این به بعد فقط آگهی‌های جدید رو می‌فرستم.",
        "en": "For “{what}” I noted the {n} current listings. From now on you'll only get new ones.",
        "fr": "Pour « {what} », j'ai noté les {n} annonces actuelles. Tu ne recevras désormais que les nouvelles.",
        "de": "Für „{what}“ habe ich die {n} aktuellen Inserate gemerkt. Ab jetzt bekommst du nur neue.",
    },
    "rep_head_init": {
        "fa": "📊 <b>گزارش راه‌اندازی</b> – منطقه: {label}",
        "en": "📊 <b>Setup report</b> – area: {label}",
        "fr": "📊 <b>Rapport de configuration</b> – zone : {label}",
        "de": "📊 <b>Einrichtungsbericht</b> – Gebiet: {label}",
    },
    "rep_head_check": {
        "fa": "📊 <b>گزارش جستجو</b> – منطقه: {label}",
        "en": "📊 <b>Search report</b> – area: {label}",
        "fr": "📊 <b>Rapport de recherche</b> – zone : {label}",
        "de": "📊 <b>Suchbericht</b> – Gebiet: {label}",
    },
    "rep_head_auto": {
        "fa": "🕒 <b>بررسی خودکار ۲ ساعته</b> – منطقه: {label}",
        "en": "🕒 <b>2-hourly check</b> – area: {label}",
        "fr": "🕒 <b>Vérification toutes les 2 h</b> – zone : {label}",
        "de": "🕒 <b>2-Stunden-Prüfung</b> – Gebiet: {label}",
    },
    "rep_first": {
        "fa": "✅ {site} ({where}): {n} آگهی فعلی (بالا فرستاده شد)",
        "en": "✅ {site} ({where}): {n} listings now (sent above)",
        "fr": "✅ {site} ({where}) : {n} annonces actuelles (envoyées ci-dessus)",
        "de": "✅ {site} ({where}): {n} aktuelle Inserate (oben geschickt)",
    },
    "rep_ok": {
        "fa": "✅ {site} ({where}): {new} آگهی جدید",
        "en": "✅ {site} ({where}): {new} new",
        "fr": "✅ {site} ({where}) : {new} nouvelles",
        "de": "✅ {site} ({where}): {new} neu",
    },
    "rep_err": {
        "fa": "❌ {site}: خطا – {err}",
        "en": "❌ {site}: error – {err}",
        "fr": "❌ {site} : erreur – {err}",
        "de": "❌ {site}: Fehler – {err}",
    },
    "rep_noloc": {
        "fa": "⚠️ منطقه در این سایت شناخته نشد، کل سوئیس",
        "en": "⚠️ area not recognised on this site, all of Switzerland",
        "fr": "⚠️ zone non reconnue sur ce site, toute la Suisse",
        "de": "⚠️ Gebiet hier nicht erkannt, ganze Schweiz",
    },
    "rep_all_ch": {
        "fa": "کل سوئیس – Ricardo فیلتر منطقه رو اجازه نمی‌ده",
        "en": "all of Switzerland – Ricardo doesn't allow an area filter",
        "fr": "toute la Suisse – Ricardo n'autorise pas de filtre de zone",
        "de": "ganze Schweiz – Ricardo erlaubt keinen Ortsfilter",
    },
    "rep_ricardo_free": {
        "fa": "ℹ️ {site}: آگهی رایگان نداره، فقط برای چیزهایی که می‌خوای جستجو می‌شه",
        "en": "ℹ️ {site}: has no free listings, so it's only searched for your wish list",
        "fr": "ℹ️ {site} : pas d'annonces gratuites, utilisé seulement pour ta liste de souhaits",
        "de": "ℹ️ {site}: keine Gratis-Inserate, wird nur für deine Wunschliste durchsucht",
    },
    "rep_off": {
        "fa": "⬜ {site}: خاموش (/sites)", "en": "⬜ {site}: off (/sites)",
        "fr": "⬜ {site} : désactivé (/sites)", "de": "⬜ {site}: aus (/sites)",
    },
    "rep_no_wishes": {
        "fa": "➕ هنوز چیزی به لیست اضافه نکردی. اسم چیزی که می‌خوای رو بفرست تا در هر سه سایت (Ricardo هم) بگردم.",
        "en": "➕ Your wish list is empty. Send the name of something you want and I'll search all three sites (Ricardo too).",
        "fr": "➕ Ta liste est vide. Envoie le nom de ce que tu cherches et je chercherai sur les trois sites (Ricardo aussi).",
        "de": "➕ Deine Wunschliste ist leer. Schick den Namen von etwas und ich suche auf allen drei Seiten (auch Ricardo).",
    },
    "rep_first_note": {
        "fa": "از این به بعد فقط آگهی‌های جدید رو می‌فرستم.",
        "en": "From now on you'll only get new listings.",
        "fr": "Désormais, tu ne recevras que les nouvelles annonces.",
        "de": "Ab jetzt bekommst du nur neue Inserate.",
    },
    "rep_head_wish": {
        "fa": "📊 <b>گزارش جستجوی چیز جدید</b> – منطقه: {label}",
        "en": "📊 <b>New item report</b> – area: {label}",
        "fr": "📊 <b>Rapport du nouvel objet</b> – zone : {label}",
        "de": "📊 <b>Bericht zum neuen Wunsch</b> – Gebiet: {label}",
    },
    "rep_ric_area": {
        "fa": "فروشنده در {label} ({d})، از روی کد پستی · از {all} نتیجه‌ی کل سوئیس",
        "en": "seller in {label} ({d}), by postcode · out of {all} results in Switzerland",
        "fr": "vendeur à {label} ({d}), selon le NPA · sur {all} résultats en Suisse",
        "de": "Verkäufer in {label} ({d}), nach PLZ · von {all} Treffern in der Schweiz",
    },
    "now_head": {
        "fa": "📋 <b>{label}</b> – {n} آگهی فعلی در منطقه‌ت، یکی‌یکی با عکس و لینک:",
        "en": "📋 <b>{label}</b> – {n} listings in your area now, one by one with photo and link:",
        "fr": "📋 <b>{label}</b> – {n} annonces dans ta zone, une par une avec photo et lien :",
        "de": "📋 <b>{label}</b> – {n} Inserate in deinem Gebiet, einzeln mit Foto und Link:",
    },
    "now_more": {
        "fa": "… {rest} آگهی دیگه هم هست. با لینک جستجوی هر سایت در گزارش پایین ببینشون.",
        "en": "… {rest} more. See them with each site's search link in the report below.",
        "fr": "… encore {rest}. Vois-les via le lien de recherche de chaque site dans le rapport ci-dessous.",
        "de": "… noch {rest} weitere. Du findest sie über den Suchlink jeder Seite im Bericht unten.",
    },
    "similar_tag": {"fa": "🔍 اسم مشابه", "en": "🔍 similar name", "fr": "🔍 nom similaire", "de": "🔍 ähnlicher Name"},
    "confirm_similar": {
        "fa": "🔍 اسم‌های مشابه: <i>{names}</i>",
        "en": "🔍 Similar names: <i>{names}</i>",
        "fr": "🔍 Noms similaires : <i>{names}</i>",
        "de": "🔍 Ähnliche Namen: <i>{names}</i>",
    },
    "ask_price": {
        "fa": "💰 بازه‌ی قیمت برای «{kw}» به فرانک؟\nمثلاً <code>20-100</code>، فقط حداکثر <code>-100</code>، فقط حداقل <code>20-</code>.\nاگه مهم نیست، «بدون محدودیت» رو بزن.",
        "en": "💰 Price range for “{kw}” in CHF?\nFor example <code>20-100</code>, max only <code>-100</code>, min only <code>20-</code>.\nIf it doesn't matter, tap “No limit”.",
        "fr": "💰 Fourchette de prix pour « {kw} » en CHF ?\nPar ex. <code>20-100</code>, max seulement <code>-100</code>, min seulement <code>20-</code>.\nSi ça n'a pas d'importance, touche « Sans limite ».",
        "de": "💰 Preisspanne für „{kw}“ in CHF?\nZ. B. <code>20-100</code>, nur Maximum <code>-100</code>, nur Minimum <code>20-</code>.\nWenn egal, tipp auf „Keine Grenze“.",
    },
    "price_skip": {"fa": "♾ بدون محدودیت", "en": "♾ No limit", "fr": "♾ Sans limite", "de": "♾ Keine Grenze"},
    "price_now": {"fa": "الان: {range}", "en": "Now: {range}", "fr": "Actuellement : {range}", "de": "Jetzt: {range}"},
    "price_bad": {
        "fa": "متوجه نشدم. مثل <code>20-100</code> یا <code>-100</code> بنویس، یا «بدون محدودیت» رو بزن.",
        "en": "I didn't get that. Write it like <code>20-100</code> or <code>-100</code>, or tap “No limit”.",
        "fr": "Je n'ai pas compris. Écris par ex. <code>20-100</code> ou <code>-100</code>, ou touche « Sans limite ».",
        "de": "Nicht verstanden. Schreib z. B. <code>20-100</code> oder <code>-100</code>, oder tipp auf „Keine Grenze“.",
    },
    "price_set": {
        "fa": "✅ قیمت «{kw}»: {range}. ⏳ الان آگهی‌های فعلی توی این بازه رو می‌فرستم.",
        "en": "✅ Price for “{kw}”: {range}. ⏳ Sending current listings in this range now.",
        "fr": "✅ Prix pour « {kw} » : {range}. ⏳ J'envoie les annonces actuelles dans cette fourchette.",
        "de": "✅ Preis für „{kw}“: {range}. ⏳ Ich schicke jetzt die aktuellen Inserate in dieser Spanne.",
    },
    "price_choose": {
        "fa": "قیمت کدوم رو می‌خوای عوض کنی؟", "en": "Which item's price range do you want to change?",
        "fr": "Pour quel objet veux-tu changer le prix ?", "de": "Für welche Sache willst du den Preis ändern?",
    },
    "price_any": {"fa": "هر قیمتی", "en": "any price", "fr": "tout prix", "de": "jeder Preis"},
    "price_from": {"fa": "از {lo} فرانک", "en": "from {lo} CHF", "fr": "dès {lo} CHF", "de": "ab {lo} CHF"},
    "price_upto": {"fa": "تا {hi} فرانک", "en": "up to {hi} CHF", "fr": "jusqu'à {hi} CHF", "de": "bis {hi} CHF"},
    "rep_sent": {
        "fa": "📨 {n} آگهی جدید فرستادم.", "en": "📨 Sent {n} new listings.",
        "fr": "📨 {n} nouvelles annonces envoyées.", "de": "📨 {n} neue Inserate geschickt.",
    },
    "free_label": {"fa": "آگهی‌های رایگان", "en": "free items", "fr": "objets gratuits", "de": "Gratis-Sachen"},
    "yes": {"fa": "✅ آره", "en": "✅ Yes", "fr": "✅ Oui", "de": "✅ Ja"},
    "no": {"fa": "❌ نه", "en": "❌ No", "fr": "❌ Non", "de": "❌ Nein"},
    "stopped": {
        "fa": "⏸ هشدارها متوقف شد. با /start دوباره شروع کن.",
        "en": "⏸ Alerts stopped. Send /start to begin again.",
        "fr": "⏸ Alertes arrêtées. Envoie /start pour recommencer.",
        "de": "⏸ Alarme gestoppt. Schick /start, um neu zu beginnen.",
    },
    "busy": {
        "fa": "یه لحظه، هنوز دارم می‌گردم…", "en": "One moment, still searching…",
        "fr": "Un instant, je cherche encore…", "de": "Moment, ich suche noch…",
    },
    "open": {"fa": "🔗 آگهی در {site}", "en": "🔗 Open on {site}", "fr": "🔗 Voir sur {site}", "de": "🔗 Auf {site} öffnen"},
    "sites": {
        "fa": "در کدوم سایت‌ها بگردم؟ با زدن روی هر سایت روشن/خاموشش کن.\n\n"
              "نکته: Ricardo فقط برای چیزهایی که خواستی جستجو می‌شه، در کل سوئیس (Ricardo اجازه‌ی فیلتر منطقه به ربات‌ها نمی‌ده و آگهی رایگان نداره).",
        "en": "Which sites should I search? Tap a site to turn it on or off.\n\n"
              "Note: Ricardo is only searched for your wish-list items, across all of Switzerland (Ricardo doesn't allow bots to filter by area, and has no free listings).",
        "fr": "Sur quels sites chercher ? Touche un site pour l'activer ou le désactiver.\n\n"
              "Note : Ricardo n'est utilisé que pour ta liste de souhaits, dans toute la Suisse (Ricardo n'autorise pas les robots à filtrer par zone et n'a pas d'annonces gratuites).",
        "de": "Auf welchen Seiten soll ich suchen? Tipp auf eine Seite, um sie ein- oder auszuschalten.\n\n"
              "Hinweis: Ricardo wird nur für deine Wunschliste durchsucht, in der ganzen Schweiz (Ricardo erlaubt Bots keinen Ortsfilter und hat keine Gratis-Inserate).",
    },
    "match": {"fa": "🔎 برای: {what}", "en": "🔎 For: {what}", "fr": "🔎 Pour : {what}", "de": "🔎 Für: {what}"},
}


def t(key, lang, **kw):
    entry = T[key]
    text = entry.get(lang) or entry["en"]
    return text.format(**kw) if kw else text
