# Prompt de résumé vidéo — Passe 2 (RESUME+NOTE+ARCHIVE)

Utilisé par le worker `researcher-videos` pour produire une note approfondie
dans `Connaissances/videos/` à partir d'un transcript JSON.

## PASSE 1 — Extraction des concepts clés

Lis l'intégralité du transcript. **Ne produis QUE la liste de concepts.**
Pas de note, pas de chapitres, pas de résumé.

Pour chaque concept transversal identifié :

```
- Titre : nom court et descriptif
- Mécanisme : 2-4 phrases expliquant le "comment" derrière le concept,
  ancrées dans des segments spécifiques du transcript
- Timestamps : 2-3 moments où ce concept apparaît ou est développé
- Claim principal : l'affirmation centrale associée
- Type d'évidence : étude_citée | raisonnement | témoignage | assertion
```

Nombre de concepts :
- Vidéo ≤45 min → 3-6 concepts
- Vidéo 45-90 min → 5-8 concepts
- Vidéo 90+ min → 8-10 concepts

## PASSE 2 — Note finale

En utilisant les concepts extraits en Passe 1 + le transcript complet,
produis la note structurée suivante :

### A) Résumé global (3-4 phrases)
- La thèse centrale + les mécanismes clés invoqués
- Pas juste "le microbiote est important" mais "le microbiote pilote
  l'inflammation via les métabolites X qui modulent la voie Y"
- Si la vidéo est en français, le résumé est en français

### B) Métadonnées
- Langue, intervenant, durée
- Source (URL si YouTube, Mega si fichier local)

### C) Concepts clés
Reprendre chaque concept de la Passe 1, développé en 1 paragraphe.
Chaque concept est un bloc autonome : un lecteur qui lit UNIQUEMENT
cette section doit tout comprendre. Inclure les mécanismes, pas juste
les conclusions.

### D) Chapitres
Tableau : | Timestamp | Titre | Affirmations clés | Mécanismes/Données |

- "Affirmations clés" : les 2-3 claims principaux du chapitre
- "Mécanismes/Données" : le "comment" derrière chaque claim
  (chiffres, protocoles, études citées, noms de chercheurs)
- Si le chapitre est purement anecdotique (témoignage personnel),
  le noter explicitement
- La redondance avec Concepts clés est assumée : ce sont deux
  parcours de lecture différents (thématique vs chronologique)

### E) Points clés (8-15)
- Chaque point : 1-2 phrases, format "[Claim] — [Mécanisme/Preuve]"
- Pas de généralités type "c'est important", "il faut écouter son corps"
- Actionnable ou contenant un mécanisme
- Liste dense, skimmable

### F) Nuances & Limites
- Ce que l'intervenant présente comme certitude vs hypothèse
- Études/papiers mentionnés (même approximativement)
- Glissements sémantiques (corrélation présentée comme causalité)
- Affirmations extraordinaires non étayées
- **Pas de fact-checking externe** — on signale ce que la vidéo
  elle-même présente ou omet, sans vérifier

### G) Extractions utiles

**Citations** — verbatim marquantes avec timestamp approximatif
```
> "citation exacte" (HH:MM:SS)
```

**Protocoles/Méthodes** — dosages, routines, pratiques concrètes mentionnées

**Références externes** — chercheurs, livres, études, institutions cités

### H) Voir aussi
- Notes liées dans le vault

## Qualité

- **Ancrage** : chaque claim doit pouvoir être rattaché à un segment du
  transcript. Pas de paraphrase vague.
- **Densité** : une note de 29 min devrait faire ~5-8 KB de markdown.
  Si elle fait 2 KB, c'est trop superficiel.
- **Langue** : la note est dans la langue de la vidéo. Si la vidéo est
  en français, tout le contenu des sections est en français (seuls les
  labels de section comme "Concepts clés" restent tels quels).
- **Ne pas halluciner de contenu** : si une section n'a pas de matière
  (ex: aucune référence externe citée), le dire sobrement ("Aucune
  référence externe citée dans la vidéo").
