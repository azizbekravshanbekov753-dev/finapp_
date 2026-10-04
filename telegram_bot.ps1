# ==========================================================
# FinApp - Professional Telegram Bot with Interactive Dialogs
# Bot: @qarz_va_harajat_bot
# Token: 8833504850:AAGzyB3hSvBV3GzEDRfTc3wlLR_IrY7FDpw
# ==========================================================

$Token = "8833504850:AAGzyB3hSvBV3GzEDRfTc3wlLR_IrY7FDpw"
$ApiUrl = "https://api.telegram.org/bot$Token"
$BaseDir = "C:\Users\ASUS\Desktop\saytlar toplami\stanford-website"
$DbFile = "$BaseDir\fin_db.json"

Write-Host "FinApp Telegram Bot ishga tushmoqda..." -ForegroundColor Green

# Klaviatura JSONlari
$GuestKeyboardJson = '{"keyboard":[[{"text":"🔐 Kirish: /login"},{"text":"📝 Royxatdan otish: /register"}]],"resize_keyboard":true}'
$MainKeyboardJson = '{"keyboard":[[{"text":"💸 Xarajat qoshish"},{"text":"🤝 Qarz qoshish"}],[{"text":"📊 Dashboard & Balans"},{"text":"🔔 Bildirishnomalar"}],[{"text":"🎯 Maqsadlar (Kopilka)"},{"text":"💳 Hamyonlar"}],[{"text":"🚪 Akkauntdan chiqish"}]],"resize_keyboard":true}'
$CancelKeyboardJson = '{"keyboard":[[{"text":"❌ Bekor qilish"}]],"resize_keyboard":true}'
$CatKeyboardJson = '{"keyboard":[[{"text":"🍔 Oziq-ovqat"},{"text":"🚕 Transport"}],[{"text":"🛍️ Xarid"},{"text":"💊 Sogliq"}],[{"text":"💡 Kommunal"},{"text":"🎮 Kongilochar"}],[{"text":"📌 Boshqa"},{"text":"❌ Bekor qilish"}]],"resize_keyboard":true}'
$DebtTypeKeyboardJson = '{"keyboard":[[{"text":"🤝 Men berdim (Qarz berish)"},{"text":"💰 Men oldim (Qarz olish)"}],[{"text":"❌ Bekor qilish"}]],"resize_keyboard":true}'
$NoDeadlineKeyboardJson = '{"keyboard":[[{"text":"Yoq (Muddatsiz)"}],[{"text":"❌ Bekor qilish"}]],"resize_keyboard":true}'

function Get-Db {
    if (Test-Path $DbFile) {
        try {
            $raw = Get-Content $DbFile -Raw -Encoding UTF8
            $obj = $raw | ConvertFrom-Json
            if (-not $obj.users) { $obj | Add-Member -NotePropertyName users -NotePropertyValue @() -Force }
            if (-not $obj.sessions) { $obj | Add-Member -NotePropertyName sessions -NotePropertyValue ([PSCustomObject]@{}) -Force }
            if (-not $obj.expenses) { $obj | Add-Member -NotePropertyName expenses -NotePropertyValue @() -Force }
            if (-not $obj.debts) { $obj | Add-Member -NotePropertyName debts -NotePropertyValue @() -Force }
            if (-not $obj.states) { $obj | Add-Member -NotePropertyName states -NotePropertyValue ([PSCustomObject]@{}) -Force }
            return $obj
        } catch { }
    }
    return [PSCustomObject]@{
        users = @()
        sessions = [PSCustomObject]@{}
        expenses = @()
        debts = @()
        goals = @()
        wallets = @()
        states = [PSCustomObject]@{}
        lastUpdateId = 0
    }
}

function Save-Db ($dbObj) {
    try {
        $json = $dbObj | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText($DbFile, $json, [System.Text.Encoding]::UTF8)
    } catch {
        Write-Host "DB saqlashda xato: $_" -ForegroundColor Red
    }
}

function Send-TgMessage ($chatId, $text, $keyboardJson = $null) {
    $escapedText = $text -replace '\\', '\\' -replace '"', '\"' -replace "`n", '\n'
    if ($keyboardJson) {
        $json = "{""chat_id"":$chatId,""text"":""$escapedText"",""parse_mode"":""HTML"",""reply_markup"":$keyboardJson}"
    } else {
        $json = "{""chat_id"":$chatId,""text"":""$escapedText"",""parse_mode"":""HTML""}"
    }
    try {
        $res = Invoke-RestMethod -Uri "$ApiUrl/sendMessage" -Method Post -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($json))
        return $res
    } catch {
        Write-Host "Xabar yuborishda xato: $_" -ForegroundColor Red
        return $null
    }
}

$db = Get-Db
Save-Db $db

$lastOffset = 0
if ($db.lastUpdateId) { $lastOffset = $db.lastUpdateId }

Write-Host "Tezkor Polling ishga tushdi (200ms)..." -ForegroundColor Green

while ($true) {
    try {
        $updatesUrl = "$ApiUrl/getUpdates?offset=$($lastOffset + 1)&timeout=1"
        $res = Invoke-RestMethod -Uri $updatesUrl -Method Get -TimeoutSec 5
        
        if ($res -and $res.ok -and $res.result) {
            foreach ($upd in $res.result) {
                $lastOffset = [math]::Max($lastOffset, [int64]$upd.update_id)
                $db.lastUpdateId = $lastOffset
                Save-Db $db

                $msg = $upd.message
                if (-not $msg -or -not $msg.text) { continue }

                $chatId = "$($msg.chat.id)"
                $rawText = $msg.text.Trim()
                $fromUser = if ($msg.from.username) { "@$($msg.from.username)" } else { $msg.from.first_name }

                # Joriy sessiya
                $currentUserId = $null
                if ($db.sessions -and $db.sessions.PSObject.Properties[$chatId]) {
                    $currentUserId = $db.sessions.$chatId
                }

                # Joriy muloqot holati
                $userState = $null
                $stateData = $null
                if ($db.states -and $db.states.PSObject.Properties[$chatId]) {
                    $userState = $db.states.$chatId.step
                    $stateData = $db.states.$chatId
                }

                # --------------------------------------------------
                # BEKOR QILISH (Har qanday bosqichda)
                # --------------------------------------------------
                if ($rawText -eq "❌ Bekor qilish" -or $rawText -eq "/cancel") {
                    if ($db.states.PSObject.Properties[$chatId]) {
                        $db.states.PSObject.Properties.Remove($chatId)
                        Save-Db $db
                    }
                    if ($currentUserId) {
                        Send-TgMessage $chatId "Amal bekor qilindi." $MainKeyboardJson
                    } else {
                        Send-TgMessage $chatId "Amal bekor qilindi." $GuestKeyboardJson
                    }
                    continue
                }

                # --------------------------------------------------
                # /START BUYRUG'I
                # --------------------------------------------------
                if ($rawText -eq "/start") {
                    if ($db.states.PSObject.Properties[$chatId]) {
                        $db.states.PSObject.Properties.Remove($chatId)
                        Save-Db $db
                    }

                    if ($currentUserId) {
                        $activeUser = $db.users | Where-Object { $_.id -eq $currentUserId } | Select-Object -First 1
                        $uName = if ($activeUser) { $activeUser.displayName } else { $fromUser }
                        $reply = "Salom, <b>$uName</b>! 👋`n`n" +
                                 "Siz <b>FinApp</b> hisobingizdasiz.`n`n" +
                                 "Quyidagi tugmalar orqali xarajat yoki qarz qo'shishingiz, balansingizni ko'rishingiz mumkin:"
                        Send-TgMessage $chatId $reply $MainKeyboardJson
                    } else {
                        $reply = "Salom, <b>$fromUser</b>! 👋`n`n" +
                                 "<b>FinApp</b> moliyaviy botiga xush kelibsiz! 💰`n`n" +
                                 "Iltimos, avval hisobingizga kiring (<b>login</b>) yoki yangi ro'yxatdan o'ting (<b>register</b>), shundan so'ng botdan to'liq foydalana olasiz:`n`n" +
                                 "👉 <b>Kirish uchun:</b>`n" +
                                 "<code>/login username parol</code>`n" +
                                 "<i>Masalan:</i> <code>/login Aziz77 123456</code>`n`n" +
                                 "👉 <b>Yangi ochish uchun:</b>`n" +
                                 "<code>/register username parol</code>`n" +
                                 "<i>Masalan:</i> <code>/register Ali 123456</code>`n`n" +
                                 "ℹ️ <i>Telegramda ochilgan akkaunt bilan saytga ham, saytdagi akkaunt bilan botga ham kirib foydalanaverasiz!</i>"
                        Send-TgMessage $chatId $reply $GuestKeyboardJson
                    }
                    continue
                }

                # --------------------------------------------------
                # /LOGIN BUYRUG'I
                # --------------------------------------------------
                if ($rawText -match "^/login\s+(?<user>[^\s]+)(\s+(?<pass>.+))?$") {
                    $uName = $Matches["user"].Trim().ToLower()
                    $pass = if ($Matches["pass"]) { $Matches["pass"].Trim() } else { "" }

                    $matchedUser = $db.users | Where-Object { $_.username.ToLower() -eq $uName } | Select-Object -First 1

                    if ($matchedUser) {
                        if ($matchedUser.password -and $pass -and $matchedUser.password -ne $pass) {
                            Send-TgMessage $chatId "❌ <b>Parol noto'g'ri!</b>`n`nIltimos, parolingizni to'g'ri kiriting:`n<code>/login $uName togri_parol</code>"
                            continue
                        }
                    } else {
                        $matchedUser = [PSCustomObject]@{
                            id = "u_" + $uName
                            username = $uName
                            displayName = ($uName.Substring(0, 1).ToUpper() + $uName.Substring(1))
                            password = $pass
                            createdAt = [DateTime]::UtcNow.ToString("o")
                        }
                        $db.users += $matchedUser
                    }

                    if (-not $db.sessions) { $db.sessions = [PSCustomObject]@{} }
                    $db.sessions | Add-Member -NotePropertyName $chatId -NotePropertyValue $matchedUser.id -Force
                    if ($db.states.PSObject.Properties[$chatId]) { $db.states.PSObject.Properties.Remove($chatId) }
                    Save-Db $db

                    $reply = "✅ <b>Muvaffaqiyatli kirdingiz!</b>`n`n" +
                             "Xush kelibsiz, <b>$($matchedUser.displayName)</b>! 👤`n" +
                             "FinApp sayti bilan 100% ulandi.`n`n" +
                             "Quyidagi tugmalar orqali moliyangizni boshqaring:"
                    Send-TgMessage $chatId $reply $MainKeyboardJson
                    continue
                }

                # --------------------------------------------------
                # /REGISTER BUYRUG'I
                # --------------------------------------------------
                if ($rawText -match "^/register\s+(?<user>[^\s]+)(\s+(?<pass>.+))?$") {
                    $uName = $Matches["user"].Trim().ToLower()
                    $pass = if ($Matches["pass"]) { $Matches["pass"].Trim() } else { "123456" }

                    $exists = $db.users | Where-Object { $_.username.ToLower() -eq $uName } | Select-Object -First 1
                    if ($exists) {
                        Send-TgMessage $chatId "⚠️ Bu foydalanuvchi nomi (<b>$uName</b>) allaqachon band!`nKirish uchun:`n<code>/login $uName parol</code>"
                        continue
                    }

                    $newUser = [PSCustomObject]@{
                        id = "u_" + $uName
                        username = $uName
                        displayName = ($uName.Substring(0, 1).ToUpper() + $uName.Substring(1))
                        password = $pass
                        createdAt = [DateTime]::UtcNow.ToString("o")
                    }
                    $db.users += $newUser
                    if (-not $db.sessions) { $db.sessions = [PSCustomObject]@{} }
                    $db.sessions | Add-Member -NotePropertyName $chatId -NotePropertyValue $newUser.id -Force
                    if ($db.states.PSObject.Properties[$chatId]) { $db.states.PSObject.Properties.Remove($chatId) }
                    Save-Db $db

                    $reply = "🎉 <b>Yangi akkaunt yaratildi va ulandi!</b>`n`n" +
                             "Foydalanuvchi: <b>$($newUser.displayName)</b>`n" +
                             "Parol: <b>$pass</b>`n`n" +
                             "🌐 Saytga kirganda ham aynan shu <b>$($newUser.username)</b> va <b>$pass</b> parolingiz bilan kirishingiz mumkin! Barchasi 100% bir xil bo'ladi."
                    Send-TgMessage $chatId $reply $MainKeyboardJson
                    continue
                }

                if ($rawText -eq "/login" -or $rawText -eq "🔐 Kirish: /login") {
                    Send-TgMessage $chatId "Akkauntga kirish uchun quyidagicha yozing:`n`n<code>/login username parol</code>`n<i>Masalan:</i> <code>/login Aziz77 123456</code>" $GuestKeyboardJson
                    continue
                }

                if ($rawText -eq "/register" -or $rawText -eq "📝 Royxatdan otish: /register") {
                    Send-TgMessage $chatId "Yangi akkaunt ochish uchun quyidagicha yozing:`n`n<code>/register username parol</code>`n<i>Masalan:</i> <code>/register Ali 123456</code>" $GuestKeyboardJson
                    continue
                }

                # --------------------------------------------------
                # AKKAUNTSIZ BO'LSA
                # --------------------------------------------------
                if (-not $currentUserId) {
                    $reply = "⚠️ <b>Siz hali akkauntingizga kirmagansiz!</b>`n`n" +
                             "Sayt bilan bir xil bo'lishi uchun hisobingizga kiring yoki yangi oching:`n`n" +
                             "👉 <b>Kirish:</b> <code>/login username parol</code>`n" +
                             "👉 <b>Yangi ochish:</b> <code>/register username parol</code>`n`n" +
                             "<i>Telegramda ochilgan akkaunt bilan saytga ham kirib foydalanaverasiz!</i>"
                    Send-TgMessage $chatId $reply $GuestKeyboardJson
                    continue
                }

                $activeUser = $db.users | Where-Object { $_.id -eq $currentUserId } | Select-Object -First 1

                # --------------------------------------------------
                # AKKAUNTDAN CHIQISH
                # --------------------------------------------------
                if ($rawText -eq "🚪 Akkauntdan chiqish" -or $rawText -eq "/logout") {
                    $db.sessions.PSObject.Properties.Remove($chatId)
                    if ($db.states.PSObject.Properties[$chatId]) { $db.states.PSObject.Properties.Remove($chatId) }
                    Save-Db $db
                    Send-TgMessage $chatId "🚪 <b>Akkauntdan chiqildi.</b>`n`nQayta kirish uchun: <code>/login username parol</code>" $GuestKeyboardJson
                    continue
                }

                # --------------------------------------------------
                # STEP-BY-STEP XARAJAT FORMASI
                # --------------------------------------------------
                if ($rawText -eq "💸 Xarajat qoshish" -or $rawText -eq "/xarajat") {
                    $db.states | Add-Member -NotePropertyName $chatId -NotePropertyValue ([PSCustomObject]@{ step = "EXP_NAME"; name = ""; amount = 0; cat = "other" }) -Force
                    Save-Db $db
                    Send-TgMessage $chatId "💸 <b>Yangi Xarajat (1/3 bosqich)</b>`n`nNimaga ishlatdingiz? (Xarajat nomini yozing, masalan: <i>Taksi, Tushlik, Bozorlik, Kofe</i>):" $CancelKeyboardJson
                    continue
                }

                if ($userState -eq "EXP_NAME") {
                    $stateData.name = $rawText
                    $stateData.step = "EXP_AMOUNT"
                    Save-Db $db
                    Send-TgMessage $chatId "💵 <b>Yangi Xarajat (2/3 bosqich)</b>`n`nXarajat: <b>$rawText</b>`n`nQancha ishlatdingiz? (Summani raqamda yozing, masalan: <i>15000</i> yoki <i>25 ming</i>):" $CancelKeyboardJson
                    continue
                }

                if ($userState -eq "EXP_AMOUNT") {
                    # Summani tahlil qilish
                    $t = $rawText.ToLower()
                    $mult = 1
                    if ($t -match "million|mln") { $mult = 1000000 }
                    elseif ($t -match "ming|min|\bk\b") { $mult = 1000 }
                    $clean = ($t -replace "[^\d.]", "")
                    $num = 0
                    if (-not [double]::TryParse($clean, [ref]$num) -or $num -le 0) {
                        Send-TgMessage $chatId "⚠️ Iltimos, summani to'g'ri raqamda yozing (masalan: <i>15000</i> yoki <i>50 ming</i>):" $CancelKeyboardJson
                        continue
                    }
                    $finalAmt = [math]::Round($num * $mult)
                    $stateData.amount = $finalAmt
                    $stateData.step = "EXP_CAT"
                    Save-Db $db

                    $amtFormatted = [string]::Format("{0:N0}", $finalAmt).Replace(",", " ") + " so'm"
                    Send-TgMessage $chatId "📂 <b>Yangi Xarajat (3/3 bosqich)</b>`n`nNomi: <b>$($stateData.name)</b>`nSumma: <b>$amtFormatted</b>`n`nToifani tanlang:" $CatKeyboardJson
                    continue
                }

                if ($userState -eq "EXP_CAT") {
                    $catMap = @{
                        "🍔 Oziq-ovqat" = "food"; "🚕 Transport" = "transport"; "🛍️ Xarid" = "shopping";
                        "💊 Sogliq" = "health"; "💡 Kommunal" = "utilities"; "🎮 Kongilochar" = "entertainment"; "📌 Boshqa" = "other"
                    }
                    $chosenCat = if ($catMap.ContainsKey($rawText)) { $catMap[$rawText] } else { "other" }

                    $todayStr = [DateTime]::UtcNow.ToString("yyyy-MM-dd")
                    $newExp = [PSCustomObject]@{
                        id = "e_tg_" + [guid]::NewGuid().ToString("N").Substring(0, 8)
                        userId = $currentUserId
                        username = $activeUser.username
                        description = $stateData.name
                        amount = $stateData.amount
                        category = $chosenCat
                        date = $todayStr
                        source = "telegram"
                        createdAt = [DateTime]::UtcNow.ToString("o")
                    }
                    $db.expenses += $newExp
                    $db.states.PSObject.Properties.Remove($chatId)
                    Save-Db $db

                    $amtFormatted = [string]::Format("{0:N0}", $stateData.amount).Replace(",", " ") + " so'm"
                    $reply = "✅ <b>Xarajat muvaffaqiyatli saqlandi!</b>`n`n" +
                             "👤 Profil: <b>$($activeUser.displayName)</b>`n" +
                             "📝 Nomi: <b>$($stateData.name)</b>`n" +
                             "💵 Summa: <b>$amtFormatted</b>`n" +
                             "📂 Toifa: <b>$rawText</b>`n" +
                             "📅 Sana: <b>Bugun</b>`n`n" +
                             "🌐 <i>Saytda ham bir zumda yangilandi!</i>"
                    Send-TgMessage $chatId $reply $MainKeyboardJson
                    continue
                }

                # --------------------------------------------------
                # STEP-BY-STEP QARZ FORMASI
                # --------------------------------------------------
                if ($rawText -eq "🤝 Qarz qoshish" -or $rawText -eq "/qarz") {
                    $db.states | Add-Member -NotePropertyName $chatId -NotePropertyValue ([PSCustomObject]@{ step = "DEBT_DIR"; type = "debt_out"; person = ""; amount = 0; deadline = "" }) -Force
                    Save-Db $db
                    Send-TgMessage $chatId "🤝 <b>Yangi Qarz (1/4 bosqich)</b>`n`nQarz turini tanlang: Siz berdingizmi yoki siz oldingizmi?" $DebtTypeKeyboardJson
                    continue
                }

                if ($userState -eq "DEBT_DIR") {
                    $isOut = $rawText.Contains("berdim")
                    $stateData.type = if ($isOut) { "debt_out" } else { "debt_in" }
                    $stateData.step = "DEBT_PERSON"
                    Save-Db $db

                    $prompt = if ($isOut) { "Kimga berdingiz? (Ismini yozing, masalan: <i>Sardor, Akam, Do'stim</i>):" } else { "Kimdan oldingiz? (Ismini yozing, masalan: <i>Akam, Shaxzod, Bank</i>):" }
                    Send-TgMessage $chatId "👤 <b>Yangi Qarz (2/4 bosqich)</b>`n`n$prompt" $CancelKeyboardJson
                    continue
                }

                if ($userState -eq "DEBT_PERSON") {
                    $stateData.person = $rawText
                    $stateData.step = "DEBT_AMOUNT"
                    Save-Db $db
                    Send-TgMessage $chatId "💰 <b>Yangi Qarz (3/4 bosqich)</b>`n`nShaxs: <b>$rawText</b>`n`nQarz summasi qancha? (masalan: <i>100000</i> yoki <i>200 ming</i>):" $CancelKeyboardJson
                    continue
                }

                if ($userState -eq "DEBT_AMOUNT") {
                    $t = $rawText.ToLower()
                    $mult = 1
                    if ($t -match "million|mln") { $mult = 1000000 }
                    elseif ($t -match "ming|min|\bk\b") { $mult = 1000 }
                    $clean = ($t -replace "[^\d.]", "")
                    $num = 0
                    if (-not [double]::TryParse($clean, [ref]$num) -or $num -le 0) {
                        Send-TgMessage $chatId "⚠️ Iltimos, summani to'g'ri raqamda yozing (masalan: <i>100000</i>):" $CancelKeyboardJson
                        continue
                    }
                    $finalAmt = [math]::Round($num * $mult)
                    $stateData.amount = $finalAmt
                    $stateData.step = "DEBT_DEADLINE"
                    Save-Db $db

                    $amtFormatted = [string]::Format("{0:N0}", $finalAmt).Replace(",", " ") + " so'm"
                    Send-TgMessage $chatId "📅 <b>Yangi Qarz (4/4 bosqich)</b>`n`nShaxs: <b>$($stateData.person)</b>`nSumma: <b>$amtFormatted</b>`n`nQaytarish muddati bormi? (Kunlar sonini yozing, masalan: <i>10 kunda</i>, yoki <i>Yoq</i> tugmasini bosing):" $NoDeadlineKeyboardJson
                    continue
                }

                if ($userState -eq "DEBT_DEADLINE") {
                    $deadline = if ($rawText -eq "Yoq (Muddatsiz)" -or $rawText.ToLower() -eq "yoq") { "Muddatsiz" } else { $rawText }
                    $todayStr = [DateTime]::UtcNow.ToString("yyyy-MM-dd")

                    $newDebt = [PSCustomObject]@{
                        id = "d_tg_" + [guid]::NewGuid().ToString("N").Substring(0, 8)
                        userId = $currentUserId
                        username = $activeUser.username
                        type = $stateData.type
                        person = $stateData.person
                        description = "$($stateData.person) ($([string]::Format('{0:N0}', $stateData.amount).Replace(',', ' ')) so'm)"
                        amount = $stateData.amount
                        deadline = $deadline
                        date = $todayStr
                        paid = $false
                        source = "telegram"
                        createdAt = [DateTime]::UtcNow.ToString("o")
                    }
                    $db.debts += $newDebt
                    $db.states.PSObject.Properties.Remove($chatId)
                    Save-Db $db

                    $dirLabel = if ($stateData.type -eq "debt_out") { "Men berdim (Qarz berish) 🤝" } else { "Men oldim (Qarz olish) 💰" }
                    $amtFormatted = [string]::Format("{0:N0}", $stateData.amount).Replace(",", " ") + " so'm"
                    $reply = "✅ <b>Qarz muvaffaqiyatli saqlandi!</b>`n`n" +
                             "👤 Profil: <b>$($activeUser.displayName)</b>`n" +
                             "🤝 Tur: <b>$dirLabel</b>`n" +
                             "👤 Shaxs: <b>$($stateData.person)</b>`n" +
                             "💰 Summa: <b>$amtFormatted</b>`n" +
                             "📅 Muddat: <b>$deadline</b>`n`n" +
                             "🌐 <i>Saytda ham darhol yangilandi!</i>"
                    Send-TgMessage $chatId $reply $MainKeyboardJson
                    continue
                }

                # --------------------------------------------------
                # DASHBOARD & BALANS
                # --------------------------------------------------
                if ($rawText -eq "📊 Dashboard & Balans" -or $rawText -eq "/balans") {
                    $todayStr = [DateTime]::UtcNow.ToString("yyyy-MM-dd")
                    $monthStr = [DateTime]::UtcNow.ToString("yyyy-MM")

                    $userExp = @($db.expenses | Where-Object { $_.userId -eq $currentUserId })
                    $todayTotal = 0
                    $monthTotal = 0
                    foreach ($e in $userExp) {
                        if ($e.date -eq $todayStr) { $todayTotal += [double]$e.amount }
                        if ($e.date -and $e.date.StartsWith($monthStr)) { $monthTotal += [double]$e.amount }
                    }

                    $openDebts = @($db.debts | Where-Object { $_.userId -eq $currentUserId -and -not $_.paid })
                    $dOut = 0; $dIn = 0
                    foreach ($d in $openDebts) {
                        if ($d.type -eq "debt_out") { $dOut += [double]$d.amount } else { $dIn += [double]$d.amount }
                    }

                    $fmtToday = [string]::Format("{0:N0}", $todayTotal).Replace(",", " ") + " so'm"
                    $fmtMonth = [string]::Format("{0:N0}", $monthTotal).Replace(",", " ") + " so'm"
                    $fmtDOut = [string]::Format("{0:N0}", $dOut).Replace(",", " ") + " so'm"
                    $fmtDIn = [string]::Format("{0:N0}", $dIn).Replace(",", " ") + " so'm"

                    $reply = "📊 <b>FinApp Moliyaviy Dashboard</b>`n" +
                             "👤 Profil: <b>$($activeUser.displayName)</b>`n" +
                             "─────────────────────`n" +
                             "💸 Bugungi xarajat: <b>$fmtToday</b>`n" +
                             "📅 Bu oylik xarajat: <b>$fmtMonth</b> ($($userExp.Count) ta yozuv)`n" +
                             "─────────────────────`n" +
                             "🤝 Berishim kerak: <b>$fmtDOut</b>`n" +
                             "💰 Olishim kerak: <b>$fmtDIn</b>`n`n" +
                             "🌐 <i>Ilova (sayt) bilan 100% bir xil!</i>"
                    Send-TgMessage $chatId $reply $MainKeyboardJson
                    continue
                }

                # --------------------------------------------------
                # BILDIRISHNOMALAR
                # --------------------------------------------------
                if ($rawText -eq "🔔 Bildirishnomalar" -or $rawText -eq "/notif") {
                    $openDebts = @($db.debts | Where-Object { $_.userId -eq $currentUserId -and -not $_.paid })
                    $notifs = @()

                    if ($openDebts.Count -gt 0) {
                        $notifs += "⚠️ Sizda <b>$($openDebts.Count) ta ochiq qarz</b> mavjud."
                    } else {
                        $notifs += "✅ Hozirda hech qanday kechiktirilgan qarz yo'q."
                    }
                    $notifs += "💡 Har kuni xarajatlaringizni bot orqali yozib boring!"

                    $reply = "🔔 <b>FinApp Bildirishnomalari:</b>`n`n" + ($notifs -join "`n`n")
                    Send-TgMessage $chatId $reply $MainKeyboardJson
                    continue
                }

                # --------------------------------------------------
                # JAMG'ARMA MAQSADLARI
                # --------------------------------------------------
                if ($rawText -eq "🎯 Maqsadlar (Kopilka)" -or $rawText -eq "/maqsadlar") {
                    $userGoals = @($db.goals | Where-Object { $_.userId -eq $currentUserId })
                    if ($userGoals.Count -eq 0) {
                        Send-TgMessage $chatId "🎯 Hozircha jamg'arma maqsadlari yo'q. Saytda yangi maqsad qo'shing!" $MainKeyboardJson
                        continue
                    }
                    $lines = @()
                    foreach ($g in $userGoals) {
                        $curStr = [string]::Format("{0:N0}", $g.currentAmount).Replace(",", " ")
                        $tgtStr = [string]::Format("{0:N0}", $g.targetAmount).Replace(",", " ") + " so'm"
                        $pct = [math]::Round(([double]$g.currentAmount / [math]::Max(1, [double]$g.targetAmount)) * 100)
                        $lines += "• <b>$($g.title)</b>: $curStr / $tgtStr (<b>$pct%</b>)"
                    }
                    $reply = "🎯 <b>Jamg'arma Maqsadlaringiz:</b>`n`n" + ($lines -join "`n")
                    Send-TgMessage $chatId $reply $MainKeyboardJson
                    continue
                }

                # --------------------------------------------------
                # HAMYONLAR
                # --------------------------------------------------
                if ($rawText -eq "💳 Hamyonlar" -or $rawText -eq "/hamyonlar") {
                    $userWallets = @($db.wallets | Where-Object { $_.userId -eq $currentUserId })
                    if ($userWallets.Count -eq 0) {
                        Send-TgMessage $chatId "💳 Hozircha hamyonlar yo'q. Saytda Hamyonlar bo'limida yangi hamyon qo'shing!" $MainKeyboardJson
                        continue
                    }
                    $lines = @()
                    foreach ($w in $userWallets) {
                        $balStr = [string]::Format("{0:N0}", $w.balance).Replace(",", " ") + " so'm"
                        $lines += "• <b>$($w.name)</b>: <b>$balStr</b>"
                    }
                    $reply = "💳 <b>Hamyonlaringiz va Balanslar:</b>`n`n" + ($lines -join "`n")
                    Send-TgMessage $chatId $reply $MainKeyboardJson
                    continue
                }

                # --------------------------------------------------
                # TEZKOR XARAJAT (Oddiy matn orqali bir qatorda yozish)
                # --------------------------------------------------
                $parsed = $null
                # Agar raqam bo'lsa
                if ($rawText -match "\d") {
                    $match = [regex]::Match($rawText.ToLower(), "(\d[\d\s,.]*)")
                    if ($match.Success) {
                        $cleanNum = $match.Groups[1].Value -replace "[\s,]", ""
                        $amt = 0
                        if ([double]::TryParse($cleanNum, [ref]$amt) -and $amt -gt 0) {
                            $mult = 1
                            if ($rawText.ToLower() -match "million|mln") { $mult = 1000000 }
                            elseif ($rawText.ToLower() -match "ming|min|\bk\b") { $mult = 1000 }
                            $amt = [math]::Round($amt * $mult)
                            $desc = ($rawText -replace "\d[\d\s,.]*(million|mln|ming|min|so['`]?m|sum|k)?", "").Trim()
                            if (-not $desc) { $desc = "Xarajat" }

                            $todayStr = [DateTime]::UtcNow.ToString("yyyy-MM-dd")
                            $newExp = [PSCustomObject]@{
                                id = "e_tg_" + [guid]::NewGuid().ToString("N").Substring(0, 8)
                                userId = $currentUserId
                                username = $activeUser.username
                                description = $desc
                                amount = $amt
                                category = "other"
                                date = $todayStr
                                source = "telegram"
                                createdAt = [DateTime]::UtcNow.ToString("o")
                            }
                            $db.expenses += $newExp
                            Save-Db $db

                            $amtStr = [string]::Format("{0:N0}", $amt).Replace(",", " ") + " so'm"
                            $reply = "✅ <b>Tezkor xarajat saqlandi!</b>`n`n" +
                                     "👤 Profil: <b>$($activeUser.displayName)</b>`n" +
                                     "📝 Nomi: <b>$desc</b>`n" +
                                     "💸 Summa: <b>$amtStr</b>`n" +
                                     "📅 Sana: <b>Bugun</b>`n`n" +
                                     "🌐 <i>Saytda ham yangilandi!</i>"
                            Send-TgMessage $chatId $reply $MainKeyboardJson
                            continue
                        }
                    }
                }

                # Agar tushunarsiz xabar kelsa
                $reply = "Salom, <b>$($activeUser.displayName)</b>! 👋`n`n" +
                         "Xarajat yoki qarz qo'shish uchun quyidagi tugmalardan birini tanlang:"
                Send-TgMessage $chatId $reply $MainKeyboardJson
            }
        }
    } catch {
        Write-Host "Xatolik: $_" -ForegroundColor DarkYellow
    }
    Start-Sleep -Milliseconds 250
}
