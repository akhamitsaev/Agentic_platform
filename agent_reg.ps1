$headers = @{
    "Authorization" = "Bearer master-secret-token-2026"
    "Content-Type" = "application/json"
}

# Poet Agent
$poet = @{
    name = "Poet Agent"
    description = "Пишет стихи"
    methods = @("write", "poem")
} | ConvertTo-Json
$poetResponse = Invoke-RestMethod -Uri "http://localhost:8001/agents" -Method POST -Body $poet -Headers $headers
Write-Host "Poet Agent ID: $($poetResponse.id)"

# Literary Translator Agent
$translator = @{
    name = "Literary Translator"
    description = "Литературный переводчик"
    methods = @("translate", "translate_poem")
} | ConvertTo-Json
$translatorResponse = Invoke-RestMethod -Uri "http://localhost:8001/agents" -Method POST -Body $translator -Headers $headers
Write-Host "Translator Agent ID: $($translatorResponse.id)"

# Orchestrator Agent
$orchestrator = @{
    name = "Orchestrator"
    description = "Оркестратор агентов"
    methods = @("generate_poems", "orchestrate")
} | ConvertTo-Json
$orchestratorResponse = Invoke-RestMethod -Uri "http://localhost:8001/agents" -Method POST -Body $orchestrator -Headers $headers
Write-Host "Orchestrator ID: $($orchestratorResponse.id)"