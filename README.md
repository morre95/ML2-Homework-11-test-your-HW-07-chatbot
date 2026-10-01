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
