$task = @{
    theme = "осенняя природа"
    count = 3
    max_stanzas = 4
    russian_style = "есенин"
    english_style = "байрон"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:8012/generate_poems" -Method POST -Body $task -ContentType "application/json"
$response