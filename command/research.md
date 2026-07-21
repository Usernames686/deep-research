---
description: Codex equivalent for /research — invoke the deep-research skill for a professional-grade report
---

<command-instruction>
For Codex, treat this file as the compatibility definition for `/research`.
Load and follow the `deep-research` skill exactly.

```text
$deep-research
```

Parse `$ARGUMENTS` to determine the research topic and optional mode flags:
- `$deep-research <topic>` or `/research <topic>` → standard mode
- `$deep-research <topic> -quick` or `/research <topic> -quick` → quick mode
- `$deep-research <topic> -deep` or `/research <topic> -deep` → deep mode
</command-instruction>

<user-request>
$ARGUMENTS
</user-request>

---
```
deep-research by hoolulu · github.com/hoolulu/deep-research
```
