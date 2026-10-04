$Token = "8833504850:AAGzyB3hSvBV3GzEDRfTc3wlLR_IrY7FDpw"
$chatId = 8378409758
$text = "Salom, Aziz77! FinApp botingiz to'liq ishlamoqda! 🎉`n`nPastdagi tugmalar orqali tekshiring:"
$GuestKeyboardJson = '{"keyboard":[[{"text":"Kirish: /login"},{"text":"Royxatdan otish: /register"}]],"resize_keyboard":true}'

$escapedText = $text -replace '\\', '\\' -replace '"', '\"' -replace "`n", '\n'
$json = "{""chat_id"":$chatId,""text"":""$escapedText"",""parse_mode"":""HTML"",""reply_markup"":$GuestKeyboardJson}"

try {
    $res = Invoke-RestMethod -Uri "https://api.telegram.org/bot$Token/sendMessage" -Method Post -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($json))
    Write-Host "Muvaffaqiyatli yuborildi: $($res.ok)" -ForegroundColor Green
} catch {
    Write-Host "Xatolik: $_" -ForegroundColor Red
}
