# Plan Wacil — partie demo-assets et soumission

Portée : uniquement le dossier demo-assets/ (conformément à CLAUDE.md et aux consignes du hackathon). Ce fichier sert de point de départ pour travailler sans perdre de temps à retrouver les détails techniques du scénario.

Objectif principal : produire les assets visibles pendant la démo, en gardant une cohérence stricte avec le scénario déjà défini par l’agent d’Alexandre / l’intégration. Le but n’est pas d’inventer une histoire différente, mais de rendre la fiction crédible, observable et vérifiable.

## 1. Principe de travail

Le contenu du récit est déjà encodé dans le pipeline de démo côté intégration. Mon rôle est de fabriquer les artefacts concrets qui rendent ce récit visible et plausible :
- une présentation de type pitch deck,
- des pages statiques publiques qui servent de fixtures,
- des fichiers de préparation pour la pseudonymisation et l’outreach,
- la checklist de soumission.

Je ne dois pas modifier les zones “contrat” du repo : web/, worker/, db/, ni modifier les fichiers qui servent de source de vérité à l’intégration.

## 2. Ce que l’agent d’Alexandre va faire

Pour éviter les conflits et les divergences, je pense toujours à ce que l’autre côté devra intégrer ensuite :
- récupérer les URLs publiques des fixtures que je déploie,
- remplacer les URLs placeholders déjà présentes dans le scénario de démo,
- brancher le rendu final du memo / du scoring / du validator sur les assets produits,
- vérifier la cohérence globale entre le deck, les sites et les données du scénario.

Donc, ma partie doit fournir des artefacts propres, stables et documentés, sans toucher au moteur de scoring ou au frontend.

## 3. Plan par tâche

### C1 · Hero pitch deck (~1.5h)

But : produire un deck de 9 slides qui sert de support visuel à la démo.

Livrables :
- un deck plausible, légèrement trop confiant, mais crédible,
- export PDF dans demo-assets/deck/.

Contenu à respecter :
- mentionner la société Ledgerline,
- faire apparaître les 4 contradictions plantées :
  1. €41K MRR en juin 2026,
  2. 12 employés,
  3. date de création contradictoire,
  4. comparable de marché mal cité,
- laisser volontairement un trou sur la cap table et sur les round terms (pas de donnée, pas de fabrication).

Important : le deck doit être cohérent avec les fixtures et avec les valeurs déjà prévues par l’intégration. Pas de chiffres différents au hasard.

### C2 · Fixture sites — critique (~2h)

But : créer de vraies pages publiques qui ressemblent à des sites d’entreprise réels, afin que le validator puisse les récupérer réellement via HTTP.

Livrables :
- au moins 3 à 5 pages statiques en HTML/CSS simples,
- déploiement sur une URL publique réelle (Vercel ou GitHub Pages),
- enregistrement des URLs dans demo-assets/FIXTURE-URLS.md.

Pages attendues :
- newsroom / legal page,
- changelog,
- team page,
- pricing page,
- customers page (si possible).

À respecter :
- le team page doit montrer 3 personnes, pas 12,
- le pricing page doit refléter des chiffres cohérents avec le scénario,
- le changelog doit montrer une activité limitée, pour appuyer la contradiction,
- la présence d’un checkout ou d’un bouton “live-looking” est utile pour donner un aspect crédible.

### C3 · Pseudonymization pass (~30min)

But : auditer le contenu du scénario pour éviter toute fuite d’identifiants réels.

Livrables :
- une liste de tous les éléments suspects dans demo-assets/PSEUDONYMIZATION.md.

Règle :
- lire web/public/demo.json uniquement comme lecteur,
- ne pas modifier web/,
- signaler les personnes ou organisations qui ne sont pas suffisamment pseudonymisées.

Les findings seront transmis à l’intégration, qui décidera du correctif final.

### C4 · Outreach copy (~30min)

But : produire un modèle de message de froid outreach, sans l’envoyer vraiment.

Livrables :
- un fichier dans demo-assets/outreach/ (par exemple northgate.md).

Contenu :
- citer l’observation déclenchante avec date et URL,
- demander une contre-preuve sur un point précis,
- garder un ton “draft, never sent”.

### C5 · Submission checklist (ongoing)

But : préparer la soumission complète du projet.

Livrables :
- compléter la checklist de docs/SUBMISSION.md,
- repérer les champs requis du portail de soumission,
- planifier la vérification depuis un clone propre au moment du freeze,
- préparer une shot list pour la vidéo de démo.

## 4. Points de dépendance avec Alexandre / l’intégration

- Les URLs réelles des fixtures doivent être fournies à l’intégration pour qu’elles remplacent les placeholders du scénario.
- Si un nombre ou un détail du scénario doit être ajusté, il faut le noter dans docs/HANDOFF.md plutôt que de le changer silencieusement.
- Le deck et les pages fixtures doivent rester cohérents entre eux, sinon la démo perd sa crédibilité.
- Les findings de pseudonymisation n’entrent pas dans ma partie d’édition, ils sont remontés à l’intégration.

## 5. Priorités et timing

Checkpoint principal : C1 + C2 doivent être terminés avant 20:00 ET / 02:00 Paris, car ils conditionnent l’enregistrement de la démo.

Ordre conseillé :
1. définir le contenu du deck et des fixtures,
2. créer les fixtures et les déployer,
3. préparer le deck,
4. faire l’audit pseudonymisation,
5. rédiger l’outreach,
6. préparer la checklist de soumission en parallèle.

Règle de travail : pousser au moins toutes les 45 minutes, et ne jamais travailler directement sur main.
