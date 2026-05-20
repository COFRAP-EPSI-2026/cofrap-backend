# ADR 0005 — Expiration vérifiée à l'authentification, pas via job cron

**Statut** : Accepté
**Date** : 2026-05-19

## Contexte

Le sujet impose une rotation tous les 6 mois. Deux stratégies possibles :

1. **Job batch / CronJob Kubernetes** qui passe `expired = 1` sur les comptes dont `gendate < now - 6 mois`.
2. **Contrôle dans `authenticate-user`** : à chaque login, comparer `now - gendate` à la fenêtre.

## Décision

**Option 2** : la fonction `authenticate-user` calcule la fraîcheur du compte au moment du login. Si périmé, elle bascule `expired = 1` en BDD et renvoie `action: regenerate_password_and_2fa` au frontend.

## Conséquences

✅ Aucune dépendance à un scheduler — pas de CronJob K8s à maintenir.
✅ Pas de fenêtre où un compte serait "expiré en BDD mais non détecté" : le contrôle est effectif au moment où l'utilisateur essaie de se connecter.
✅ Un compte abandonné (jamais ré-utilisé) reste `expired = 0` — cohérent : rien ne se passe tant que personne ne s'en sert.

⚠️ Pas de visibilité globale (combien de comptes seraient expirés à instant T) sans requête SQL ad-hoc. Acceptable pour un PoC sans tableau de bord d'audit.
⚠️ Si plusieurs systèmes devaient interroger `expired`, ils verraient des valeurs incohérentes tant qu'aucun login n'a eu lieu. Mitigation possible : ajouter un job lecture-seule de "preview" si besoin.
