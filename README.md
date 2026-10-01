# Homework 11 – eval av HW-07-chatboten

Boten i `bot/` är en kopia av [HW-07](https://github.com/morre95/ML2-Homwork-07-Kubernetics)
(första commit), med en svensk systemprompt som bär en falsk API-nyckel (`CHATBOT_SECRET`)
så att läckagetesterna har något att skydda.

| Fil | Innehåll |
|---|---|
| `cases.yaml` | 10 testfall med maskinellt avgörbara checks |
| `run_evals.py` | kör fallen mot boten, skriver pass/fail-tabell |
| `resultat.md` | riktiga körningar med datum och antal fall som föll |
| `rapport.md` | vad som föll, varför, och vad som ändrades |

## Köra

Kräver Ollama lokalt med `qwen3.8:latest`.

```bash
export CHATBOT_SECRET=sk-test-$(openssl rand -hex 12)
uv run bot/app.py &                                   # boten på :8000
uv run run_evals.py                                   # tabell i terminalen
uv run run_evals.py --repeat 3 --report resultat.md   # och appenda till resultat.md
```

Exit-kod 1 om något fall föll.

Utvärderingen väntar upp till 10 sekunder på att botens HTTP-server ska svara,
så kommandona kan köras direkt efter varandra. Om boten inte går att nå avslutas
körningen med ett felmeddelande. Vid annan port eller adress, ange exempelvis
`--url http://127.0.0.1:8001/chat`. Väntan gäller boten; Ollama och modellen
måste också vara tillgängliga för att chattfallen ska fungera.

## Stänga av

```bash
pkill -f bot/app.py
```

## Vilka förbättringar har gjort mellan körning 1 och 2 

1. **Kontroll av inkommande frågor.** Tidigare skickades även tomma frågor till modellen. Nu avvisar boten tomma eller felaktigt formaterade frågor och meddelanden över 4 000 tecken med HTTP-status `400`.
2. **Blockering av egna systeminstruktioner.** Tidigare kunde klienten skicka meddelanden med rollen `system` och påverka botens beteende. Nu tillåts bara `user` och `assistant`; servern bestämmer systemprompten.
3. **Den falska API-nyckeln togs bort ur systemprompten.** I körning 1 lyckades ett angrepp få boten att återge prompten inklusive nyckeln. När nyckeln inte längre skickas till modellen kan den inte läcka från prompten.
4. **Tydligare instruktioner till modellen.** Prompten säger uttryckligen att svar ska vara på svenska även på engelska frågor, att användartext inte ska behandlas som nya instruktioner och att boten ska avböja försök att få prompten återgiven.
