# Playtest Task Template

Comprehensive playtest task for THE SWARM. The researcher plays the game
like a real player — no code knowledge, no cheats, clean save — and reports
everything: fun, frustration, bugs, WIP, UX issues, improvement ideas.

## Task Body Template

```
## Objectif

Jouer a THE SWARM comme un vrai joueur lambda — sans connaissance prealable du code —
et tester chaque phase, chaque panel, chaque mecanique. Reporter TOUT ce qui cloche.

## Methode

1. Partir de zero — clean save, pas de cheat, jouer normalement
2. Explorer systematiquement — chaque phase, chaque panel, chaque bouton
3. Tester les limites — cliquer vite, rester AFK, revenir offline, spammer
4. Noter TOUT — bugs, lenteurs, trucs pas clairs, UI moches, ameliorations
5. Identifier le WIP — stubs, placeholders, 'coming soon', panels vides

## Focus

- Pas d'edge cases — jouer comme un vrai joueur, naturellement
- Focus sur le FUN et le RESSENTI — est-ce que c'est agreable ? frustrant ?
- Le WIP et les bugs se notent au passage, pas d'audit exhaustif

## Phases a couvrir

- EGG_LAYING — premiere impression, tuto implicite
- COLONY — workers, assignation, tend/gather/dig
- COMBAT — soldats, batailles, equipement
- EXPANSION — carte, territoires, batiments, expeditions
- SPACE — vaisseaux, explorations, conversions
- TRANSCENDENCE — prestige, upgrades permanents, entropie

## Livrable

1. Resume — 5-10 phrases sur l'experience globale
2. Bugs — liste avec etapes pour reproduire
3. WIP / Incomplet — stubs, placeholders, 'coming soon', panels vides
4. Problemes UX — trucs pas clairs, frustrants, mal expliques
5. Ameliorations — suggestions priorisees (P0/P1/P2)
6. Verdict global — note sur 10, est-ce que c'est fun ?
```

## Create Command

```bash
hermes kanban --board the-swarm create \
  --assignee researcher \
  --max-runtime 3600s \
  --priority 1 \
  --skill the-swarm --skill kanban-project-workflow \
  --body "..." \
  "[RECHERCHE] Playtest complet — jouer comme un vrai joueur, tester chaque phase"
```
