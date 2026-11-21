# Jev + OpenCode — configuración y uso

**Fecha** 2026-11-21 · **Verificado en** `main` `1cdb221` (catpart-parser) · **Host** OpenCode (T3 Code / OpenCode harness)
**Alcance** instalar el skill `jev`, configurar el CLI, elegir una ruta de servicio, usarlo desde OpenCode y ejecutar un smoke test real.

---

## 0. Modelo mental: tres rutas que no se mezclan

Jev no es un chat: es un servicio de **decisiones tipadas** (`choice`, `noul`, `score`). Hay tres formas de usarlo y **no comparten clave, modelo ni contrato**:

| Ruta | Qué usa | Clave | Modelo(s) | Salida |
| :--- | :--- | :--- | :--- | :--- |
| **A. Skill + Jev API** | `jev-decide` → OpenRouter o TypeSafe | `OPENROUTER_API_KEY` **o** `TYPESAFE_API_KEY` | `typesafe/jev-1.13` (OpenRouter) · `jev-1.13.0` (TypeSafe) | probabilidades calibradas + `decisions[].status` (`selected` / `needs_review`) |
| **B. OpenCode System One** | HTTP directo a `/inference/systemone/v1/systemone` | `OPENCODE_API_KEY` o archivo externo 600 | `jev-1.13-free` (free tier) · `jev-1.13` (pago) | `answers` crudas (`choice` + `probabilities`, `noul`, `score`) + `usage` |
| **C. Simulación** | el agente/modelo actual de OpenCode | ninguna clave Jev | el modelo elegido | `jev_called:false`, `probability:null`, `confidence:null` — **no es Jev** |

Regla de oro: **elige una ruta y no cambies por error**. Un 401/402/429 no autoriza a cambiar de proveedor ni a inventar una respuesta.

---

## 1. Prerrequisitos

- OpenCode funcionando y una sesión con acceso a skills.
- Python **3.10+** (`python3 --version`; en esta máquina 3.14.10).
- `uv` para instalar el CLI (opcional: el skill trae `scripts/jev.py`).
- Red hacia el proveedor elegido.
- Una clave:
  - Ruta A: OpenRouter (`https://openrouter.ai/settings/keys`) o TypeSafe (`https://console.typesafe.ai`).
  - Ruta B: OpenCode API key de la consola; `jev-1.13` requiere créditos, `jev-1.13-free` no.
- No hace falta MCP ni servidor local.

---

## 2. Instalar el skill en OpenCode

OpenCode descubre skills en estas rutas (documentación oficial):

| Scope | Rutas |
| :--- | :--- |
| Global (nativa) | `~/.config/opencode/skills/<id>/SKILL.md` |
| Global (compatibilidad) | `~/.claude/skills`, `~/.agents/skills` |
| Proyecto (nativa) | `.opencode/skills/<id>/SKILL.md` |
| Proyecto (compatibilidad) | `.claude/skills`, `.agents/skills` |

En esta máquina el skill ya está instalado en la ruta de compatibilidad `~/.agents/skills/jev`. Para una instalación nueva, usa la ruta nativa global:

```bash
git clone --depth 1 https://github.com/wuyoscar/jev-skill /tmp/jev-skill
mkdir -p ~/.config/opencode/skills
cp -R /tmp/jev-skill/skills/jev ~/.config/opencode/skills/jev
```

Si prefieres la ruta de compatibilidad que ya usa este host, cambia el destino a `~/.agents/skills/jev` (es la que está activa hoy).

Variantes opcionales (entry points independientes, no se encadenan solas):

```bash
for s in jev-triage jev-documents jev-eval jev-act; do
  cp -R "/tmp/jev-skill/skills/$s" ~/.config/opencode/skills/
done
```

Verificación:

```bash
ls ~/.config/opencode/skills/jev/SKILL.md   # o ~/.agents/skills/jev/SKILL.md
```

Luego, en OpenCode:

- pide al agente **“load the `jev` skill”**, o
- comprueba que `jev` aparece en la lista de skills de la sesión.

El **ID es el nombre del directorio** (`jev`), no el `name` del frontmatter; es *case-sensitive*. Si no aparece: revisa que el archivo se llame exactamente `SKILL.md`, que tenga `description`, que no haya un `opencode/autoinvoke: false`, y reinicia la sesión/el host para que refresque el catálogo.

---

## 3. Instalar el CLI

```bash
uv tool install jev-skill
```

Deja `jev-decide` en `~/.local/bin/jev-decide` (symlink al entorno de `uv`). Verifica:

```bash
command -v jev-decide
jev-decide --help
jev-decide setup
```

`jev-decide setup` solo comprueba **presencia** de claves; **no** valida créditos, no autentica y no hace red. En esta máquina, sin claves A, devuelve `available.openrouter=false`, `available.typesafe=false`.

Si no usas `uv`, el script bundled funciona igual:

```bash
python3 ~/.agents/skills/jev/scripts/jev.py setup
```

---

## 4. Ruta A — OpenRouter o TypeSafe (Jev API)

### 4.1 Elegir proveedor y clave

Elige **uno** y pasa siempre `--provider`:

| Proveedor | Variable | Key page | `--provider` | Modelo |
| :--- | :--- | :--- | :--- | :--- |
| OpenRouter | `OPENROUTER_API_KEY` | https://openrouter.ai/settings/keys | `openrouter` | `typesafe/jev-1.13` |
| TypeSafe | `TYPESAFE_API_KEY` | https://console.typesafe.ai | `typesafe` | `jev-1.13.0` (mapea el ID bundled) |

Configura la clave **en el entorno que lanza OpenCode**, nunca en el chat ni en un archivo del repo:

```bash
export TYPESAFE_API_KEY="<tu-clave>"
# o
export OPENROUTER_API_KEY="<tu-clave>"
```

Notas:

- El CLI **no auto-carga `.env`**.
- Un OpenCode ya abierto puede no heredar la variable: reinícialo.
- No imprimas la variable para depurar; `jev-decide setup` solo dice presente/ausente.
- Una clave placeholder “presente” sigue siendo inválida: el setup no la autentica.

### 4.2 Dry-run y llamada real

```bash
# Validación offline: no llama a la API, no gasta
jev-decide decide request.json --provider typesafe --dry-run

# Llamada real (solo con aprobación para ese input y ese gasto)
jev-decide decide request.json --provider typesafe > result.json
```

`--dry-run` devuelve 0 si el JSON es válido; **no es un juicio**. La llamada real devuelve:

- **0** = decisión `selected`/`scored`.
- **2** = alguna decisión queda `needs_review`.
- **1** = error de input, red, HTTP o parseo.

Umbrales conservadores por defecto: `--min-probability 0.8`, `--min-margin 0.15`. Puedes forzar revisión de etiquetas con `--review-label`.

### 4.3 Clasificar un texto (atajo)

```bash
jev-decide classify \
  --text "Me cobraron dos veces la suscripción; quiero el reembolso." \
  --criteria labels.json \
  --provider typesafe
```

`labels.json` es un objeto `{"label": "descripción", ...}`. No es una decisión de acción: el host valida y decide.

### 4.4 Interpretación

- `status: selected` significa “el modelo prefiere esta etiqueta con margen”, **no** permiso para ejecutar nada.
- `probability` y `confidence` **no son accuracy**.
- `needs_review` es una salida de primera clase: no la fuerces a una etiqueta.
- El modelo no hereda el contexto de OpenCode: todo lo que necesita va en `state` y `questions`.

---

## 5. Ruta B — OpenCode System One (la que usa catpart-parser)

Esta es la ruta de `scripts/triage/jev_arbiter.py` y del benchmark S8/L5. No necesita OpenRouter ni TypeSafe; usa la key de OpenCode.

### 5.1 Clave

```bash
export OPENCODE_API_KEY="<tu-clave>"
# o un archivo externo, permisos 600:
install -m 600 /dev/null /tmp/oc_key.txt
# pega la clave dentro del archivo, nunca en el chat ni en el repo
```

`scripts/jev_opencode_smoke.py` acepta `--key-file`; `scripts/triage/run_triage.py` también, y el árbitro resuelve la clave desde `OPENCODE_API_KEY` o ese archivo. Las claves nunca se hardcodean, ni se commitean, ni se leen desde dentro del repo.

### 5.2 Endpoint y modelos

```
POST https://opencode.ai/inference/systemone/v1/systemone
Authorization: Bearer <key>
Content-Type: application/json
User-Agent: opencode/2.3.2 (tu cliente)
x-opencode-session: ses_<id>
```

| Modelo | Cuándo | Coste |
| :--- | :--- | :--- |
| `jev-1.13-free` | smoke test, triage mientras el free tier esté disponible | `usage.cost = 0` |
| `jev-1.13` | uso de producción | pago; sin créditos devuelve **402 Insufficient balance** |

`jev-1.13` **no** es un modelo de chat de OpenCode Go; es un modelo System One del endpoint de inferencia. No lo busques en el catálogo de chat.

### 5.3 Contrato

```json
{
  "model": "jev-1.13-free",
  "state": "texto, objeto JSON o array de evidencia",
  "questions": {
    "route_bucket": {
      "type": "choice",
      "instructions": "Route this file into exactly one bucket.",
      "criteria": {
        "already_healthy": "parsed clean, real mesh",
        "known_feature_only": "display only by design",
        "needs_new_re_subagent": "real decoding failure"
      }
    },
    "escalate_to_system2": {
      "type": "noul",
      "instructions": "True only if this needs deeper analysis."
    },
    "visual_fidelity_risk": {
      "type": "score",
      "instructions": "Risk that a rendered view misrepresents the part.",
      "criteria": ["1 faithful", "2 benign artifact", "3 nothing real", "4 large loss", "5 severe holes"]
    }
  }
}
```

Respuesta real (recortada) del smoke test:

```json
{
  "model": "jev-1.13-free",
  "answers": {
    "route_bucket": {
      "type": "choice",
      "choice": "already_healthy",
      "confidence": 1,
      "probabilities": {"already_healthy": 1, "known_feature_only": 0, "needs_new_re_subagent": 0}
    },
    "escalate_to_system2": {"type": "noul", "noul": 0.2},
    "visual_fidelity_risk": {
      "type": "score",
      "score": 0.03,
      "confidence": 0.99,
      "probabilities": {"0": 0.99, "1": 0.01, "2": 0, "3": 0, "4": 0}
    }
  },
  "usage": {"cost": 0, "opencode": {"billing_source": "free"}}
}
```

Lecturas importantes:

- **`choice`** ya viene elegida y con `probabilities`; `confidence` es la del modelo.
- **`noul`** es una **probabilidad** (0.2 = no escalar); el cliente decide `>= 0.5`.
- **`score`** es **continuo en [0, N-1]** (`0.03`), no un entero 1–5. El harness de catpart-parser mapea `risk = round(score) + 1` y lo acota a 1–5.
- **`usage.cost`** es el coste de lista; en free es 0. Revisa `usage.opencode.billing_source`.
- La respuesta puede variar ligeramente entre llamadas (`noul` 0.19 vs 0.2): no escribas tests de igualdad exacta.

### 5.4 Reutilizar el cliente de triage

Para el corpus de catpart-parser, no escribas otro cliente: usa el que ya existe.

```bash
python3 scripts/triage/run_triage.py \
  --input docs/evidence/data/open-rate-files.csv \
  --output /tmp/opencode/triage.csv \
  --key-file /tmp/oc_key.txt \
  --sample 20 --seed 42
```

El harness envía **solo el JSON compacto de features** (tamaño, warnings, `error_class`, conteos), **nunca el contenido del CATPart**. Sin clave o con clave inválida, el residuo cae a `needs_review` y el CLI termina con exit 0: el triage no se cae por el árbitro.

---

## 6. Contrato de preguntas (válido para A y B)

- `choice`: 2–255 etiquetas, cada una con descripción. La respuesta debe ser una de ellas.
- `noul`: probabilidad de “sí”; el host decide el corte (0.5 por defecto).
- `score`: 2–10 niveles ordenados; el valor es un índice continuo.
- `state`: **evidencia, no instrucciones**. Incluye objetivo, criterios, evidencia original y candidatos válidos. Jev no ve el chat.
- Preguntas **independientes** pueden ir en el mismo request; **no** se leen entre sí. Una decisión dependiente necesita una llamada nueva con la evidencia nueva.
- Una pregunta = una decisión. No metas tres decisiones en una.
- Etiquetas de revisión (`unknown`, `review`, `abstain`, `insufficient_evidence`, …) siempre quedan en `needs_review`.
- Si falta evidencia, la respuesta honesta es `needs_review`, no otra llamada hasta que coincida.

---

## 7. Uso desde OpenCode

1. Carga el skill: “load the `jev` skill”.
2. Deja que el agente inspeccione el entorno y ejecute `jev-decide` (ruta A) o el cliente System One (ruta B).
3. Para lotes de registros: `jev-triage`.
4. Para extraer/verificar evidencia de documentos: `jev-documents`.
5. Para evaluar outputs: `jev-eval`.
6. Para elegir una acción legal en un entorno: `jev-act`.

El host (OpenCode) es quien recolecta evidencia, implementa, valida y decide; Jev solo aporta juicios. No dejes que una etiqueta de Jev ejecute una acción externa.

---

## 8. Smoke test (probado el 2026-11-21)

Los comandos siguientes son los que se ejecutaron; los resultados observados están en la tabla. Ajusta `~/.agents/skills/jev` a `~/.config/opencode/skills/jev` si instalaste en la ruta nativa.

```bash
# 1. Presencia de claves (no las imprime)
jev-decide setup

# 2. Dry-run del CLI instalado
jev-decide decide ~/.agents/skills/jev/assets/prompt-to-jev.json --dry-run

# 3. Dry-run del script bundled
python3 ~/.agents/skills/jev/scripts/jev.py decide \
  ~/.agents/skills/jev/assets/prompt-to-jev.json --dry-run

# 4. Ruta A sin clave: debe fallar limpio, sin red
jev-decide decide ~/.agents/skills/jev/assets/prompt-to-jev.json --provider typesafe

# 5. Ruta B free: llamada real, coste 0
python3 scripts/jev_opencode_smoke.py --key-file /tmp/oc_key.txt

# 6. Ruta B pago: sin créditos debe dar 402
python3 scripts/jev_opencode_smoke.py --key-file /tmp/oc_key.txt --model jev-1.13
```

Resultados observados:

| # | Comando | Resultado |
| :--- | :--- | :--- |
| 1 | `jev-decide setup` | exit 0; `available.openrouter=false`, `available.typesafe=false` en esta máquina; `jev_called=false` |
| 2 | `jev-decide ... --dry-run` | exit 0; imprime el request con `model: typesafe/jev-1.13`; sin red |
| 3 | `python3 .../jev.py ... --dry-run` | exit 0; mismo contrato |
| 4 | `jev-decide ... --provider typesafe` sin clave | exit 1; `Set TYPESAFE_API_KEY in the calling process environment; run setup for choices` |
| 5 | `scripts/jev_opencode_smoke.py --key-file /tmp/oc_key.txt` | **HTTP 200**, ~172–217 ms; `choice=already_healthy`, `confidence=1`, `noul=0.19–0.2`, `score=0.03` → `risk=1`, `usage.cost=0` |
| 6 | `... --model jev-1.13` | **HTTP 402** `Insufficient balance` (~121–126 ms); no se reintenta ni se cambia de proveedor |
| 7 | `python3 scripts/triage/run_triage.py --input docs/evidence/data/open-rate-files.csv --output /tmp/opencode/triage_smoke.csv --key-file /tmp/oc_key.txt --sample 1 --seed 42` | exit 0; 1.440 deterministas, 2 residuo, 1 arbitrado por jev, 0 errores, `list_cost $0.000000` (se usó `--sample 1` para el smoke; el doc muestra 20) |

No probado en esta máquina: una llamada real de la **ruta A** (OpenRouter/TypeSafe), porque no hay `OPENROUTER_API_KEY` ni `TYPESAFE_API_KEY` en el entorno. El dry-run y el fallo limpio sin clave sí están verificados. Para completar la prueba A: exporta una clave, reinicia OpenCode y ejecuta el comando 2 sin `--dry-run`.

---

## 9. Troubleshooting

| Síntoma | Causa probable | Qué hacer |
| :--- | :--- | :--- |
| `available:false` en `setup` | variable no exportada en el proceso de OpenCode, o host ya abierto | exporta la clave, reinicia OpenCode; comprueba presencia, no el valor |
| `Set TYPESAFE_API_KEY...` / `Set OPENROUTER_API_KEY...` | falta la clave del `--provider` elegido | configura la clave correcta; no cambies de proveedor por el error |
| **401** | clave inválida/expirada | rota la clave en la consola; no la pegues en el chat |
| **402** | sin créditos (ruta B pago, o cuenta A sin saldo) | usa `jev-1.13-free` o recarga; 402 no autoriza fallback |
| **403** | clave sin permiso para el modelo/endpoint | revisa el plan/permisos; no reintentes a ciegas |
| **429 / 5xx / timeout** | rate limit o servicio | backoff exponencial, máx. 3 reintentos; si persiste, `needs_review` |
| Respuesta no parseable | drift de contrato | 1 reintento; si falla, `needs_review`; no inventes la etiqueta |
| `--dry-run` “pasa” pero la llamada real falla | el dry-run no autentica ni valida créditos | prueba una llamada real mínima; revisa 401/402 |
| El skill no aparece en OpenCode | ruta incorrecta o catálogo no refrescado | `~/.config/opencode/skills/jev/SKILL.md` o `~/.agents/skills/jev/SKILL.md`; reinicia la sesión |
| `model not found` en OpenRouter/TypeSafe | ID de modelo de la otra ruta | A: `typesafe/jev-1.13` / `jev-1.13.0`; B: `jev-1.13` / `jev-1.13-free` |
| `.env` no se lee | el CLI no auto-carga `.env` | exporta en el entorno del host o usa el gestor de secretos |

---

## 10. Seguridad y coste

- Claves **fuera del repo**, permisos `600`; nunca en `AGENTS.md`, chats, logs ni commits.
- `/tmp/oc_key.txt` es transitorio: al reiniciar desaparece. Si el triage pasa a producción, muévela al almacén de secretos del host.
- Las llamadas reales **cuestan**; el free tier puede agotarse o desaparecer. No hay fallback automático.
- No envíes datos privados sin aprobación. El harness de catpart-parser envía solo features compactas, nunca el binario.
- Registra estado, latencia y coste; no registres cuerpos con credenciales.
- Un error del proveedor no es permiso para cambiar de servicio ni para simular y presentarlo como Jev.

---

## 11. Límites medidos (catpart-parser, 2026-11-21)

- `jev-1.13-free` en el benchmark balanceado S8: **78,3 %** de accuracy de ruta (47/60).
- El mismo modelo en el **residuo real** L5: **34,5 %** (48/139); su error dominante es mandar `already_healthy` a `known_seam_not_manifold` (85/139) con risk 4–5.
- Por eso **no se conserva como árbitro fijo**: el router determinista cubre 1.823/2.199 = 82,9 %; el residuo (376) va a reglas deterministas o `needs_review`.
- Jev es una ayuda de juicio, no el harness. La confianza no es accuracy y una selección no es permiso.

---

## 12. Checklist de cierre

- [ ] Skill en `~/.config/opencode/skills/jev/SKILL.md` (o `~/.agents/skills/jev/SKILL.md`) y visible en OpenCode.
- [ ] `jev-decide` en PATH (`command -v jev-decide`).
- [ ] `jev-decide setup` responde (aunque sea `false`).
- [ ] Dry-run de `prompt-to-jev.json` con exit 0.
- [ ] Ruta elegida (A o B) y clave configurada en el entorno correcto.
- [ ] Smoke test real de la ruta elegida (free o pago) con resultado y coste.
- [ ] Clave fuera del repo y sin imprimir en logs.
- [ ] Fallback `needs_review` verificado.
