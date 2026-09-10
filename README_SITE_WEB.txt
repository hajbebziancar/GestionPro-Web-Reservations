GESTIONPRO - SITE WEB PROFESSIONNEL HBZ RENT CAR
=================================================

DEMARRAGE
---------
1) Ouvrir le dossier site_web.
2) Double-cliquer sur DEMARRER_SITE.bat.
3) Site public : http://127.0.0.1:5000
4) Administration : http://127.0.0.1:5000/admin
5) Gestion du parc : http://127.0.0.1:5000/admin/parc

NOUVELLE GESTION DU PARC
------------------------
- Ajouter un véhicule depuis l'administration Web.
- Modifier marque, immatriculation, châssis, prix/jour, compteur et état.
- Ajouter une photo JPG/PNG/WEBP affichée sur le site public.
- Filtrer le parc par recherche et état EN SERVICE / HORS SERVICE.
- Supprimer un véhicule sans historique.
- Si le véhicule possède déjà une location ou réservation, la suppression destructive est bloquée : le véhicule passe HORS SERVICE afin de conserver l'historique GestionPro.
- Les véhicules EN SERVICE sont automatiquement visibles sur le site public.

RESERVATIONS
------------
- Le site vérifie les chevauchements avec les réservations et locations existantes.
- Les formats de date GestionPro DD/MM/YYYY et Web YYYY-MM-DD sont tous deux pris en charge.
- Une demande valide est ajoutée à la table reservations avec le statut EN ATTENTE.
- L'administrateur peut confirmer ou annuler les demandes.

SECURITE
--------
- Mot de passe administrateur hashé.
- Protection CSRF.
- Session HttpOnly / SameSite.
- Validation des saisies et des photos.
- Journal d'audit Web.
- Le serveur de test reste limité à 127.0.0.1.

IMPORTANT POUR INTERNET
-----------------------
Ne pas ouvrir directement le port 5000 sur Internet. Pour une publication réelle, utiliser HTTPS et un hébergement/reverse proxy sécurisé. Le fichier gestion.db du PC ne doit pas être exposé publiquement.

VERSION INTERNET / SYNCHRONISATION
----------------------------------
- Serveur de production Waitress inclus : production_server.py.
- Dockerfile et docker-compose.yml inclus.
- Variables de sécurité dans .env.example.
- API privée par Bearer token pour synchroniser le parc et les réservations.
- Le fichier de base du PC n'est jamais exposé sur Internet.
- Voir DEPLOIEMENT_INTERNET.txt.
