# Live Crete Events Scraper

**Scraper ultra-performant et robuste pour 202 sources d'événements en Crète**

Système professionnel de scraping automatique pour collecter, traduire et importer des événements depuis 202 sources (sites web + Facebook) vers WordPress.

## Fonctionnalités Principales

### 🚀 Scraping Multi-Sources
- **202 sources** : Sites web et pages Facebook
- **Multi-threading** : Jusqu'à 5 scrapers parallèles pour performance maximale
- **Scraping intelligent** : Détection automatique (Selenium vs requests)
- **Facebook** : Connexion persistante avec cookies, scraping événements publics

### 🔒 Sécurité & Anti-Blocage
- **Rotation User-Agent** : Pool de 50+ agents aléatoires
- **Stealth Mode** : Protection complète anti-détection
  - navigator.webdriver = false
  - Canvas fingerprinting defense
  - WebGL fingerprinting defense
  - Random viewport sizes
- **Délais aléatoires** : 3-10 secondes entre requêtes
- **Retry avec backoff exponentiel** : Gestion automatique des erreurs

### 🌍 Traduction Automatique
- **Grec/Anglais → Français** avec deep-translator
- **Détection automatique** de la langue source
- **10 champs traduits** :
  - title, subtitle, description, excerpt
  - venue_name, venue_address, venue_city
  - organizer_name, category, tags

### 📸 Gestion Images
- **Téléchargement automatique** depuis toutes les sources
- **3 tailles générées** :
  - Full: 1200x800px
  - Medium: 600x400px
  - Thumbnail: 300x200px
- **Optimisation** : Compression JPEG qualité 85%
- **Prêt pour WordPress** : Upload direct dans médiathèque

### ✅ Qualité des Données
- **Validation stricte** : Dates, URLs, emails
- **Nettoyage HTML** : Suppression tags, whitespace
- **Géolocalisation** : Coordonnées GPS automatiques (Nominatim)
- **Déduplication** : Détection similarité à 85%
- **Slugification** : URLs SEO-friendly

### 💾 Export & Import
- **Export CSV** : 48 colonnes (38 originales + 10 traduites)
- **Import WordPress** : API REST avec The Events Calendar
- **Backups automatiques** : JSON compressé (gzip)
- **Cache intelligent** : Évite re-scraping (TTL 24h)

## Architecture

```
live-crete-scraper/
├── src/                          # Modules Python
│   ├── __init__.py
│   ├── selenium_manager.py       # Gestion Selenium anti-détection
│   ├── facebook_scraper.py       # Scraping Facebook
│   ├── web_scraper.py            # Scraping sites web
│   ├── translator.py             # Traduction deep-translator
│   ├── image_handler.py          # Téléchargement & redimensionnement
│   ├── data_processor.py         # Validation, géolocalisation, dédup
│   ├── csv_exporter.py           # Export CSV
│   └── cache_manager.py          # Cache & retry logic
├── data/
│   ├── output/                   # CSV exportés
│   ├── cache/                    # Cache disque
│   ├── backups/                  # Backups JSON
│   └── logs/                     # Logs de scraping
├── images/events/                # Images téléchargées
│   ├── full/
│   ├── medium/
│   └── thumbnail/
├── cookies/                      # Cookies Facebook
├── main.py                       # Script principal
├── import_to_wordpress.py        # Import WordPress
├── config.json                   # Configuration centralisée
├── sources_config_complete.csv   # 202 sources
├── requirements.txt              # Dépendances Python
├── setup.sh                      # Installation automatique
├── run.sh                        # Lancement rapide
└── README.md
```

## Installation

### Prérequis
- **Python 3.8+**
- **Chrome/Chromium** (pour Selenium)
- **4GB RAM minimum** (pour multi-threading)

### Installation Automatique

```bash
# Cloner le dépôt
git clone <repository-url>
cd live-crete-scraper

# Lancer l'installation
chmod +x setup.sh
./setup.sh
```

Le script `setup.sh` va :
1. Vérifier Python 3
2. Créer un environnement virtuel
3. Installer toutes les dépendances
4. Vérifier Chrome/Chromium
5. Créer tous les dossiers nécessaires

### Installation Manuelle

```bash
# Créer environnement virtuel
python3 -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate

# Installer dépendances
pip install -r requirements.txt

# Créer dossiers
mkdir -p data/output data/cache data/backups data/logs
mkdir -p images/events/full images/events/medium images/events/thumbnail
mkdir -p cookies
```

## Configuration

### 1. Configurer config.json

Éditer `config.json` pour personnaliser les paramètres :

```json
{
  "facebook": {
    "email": "votre-email@example.com",
    "password": "votre-mot-de-passe"
  },
  "wordpress": {
    "site_url": "https://votre-site-wordpress.com",
    "username": "votre-username",
    "password": "votre-application-password"
  },
  "performance": {
    "max_workers": 5  // Nombre de threads parallèles
  },
  "translation": {
    "enabled": true,
    "target_language": "fr"
  }
}
```

### 2. Configurer les Sources

Le fichier `sources_config_complete.csv` contient les 202 sources :

```csv
source_id,source_name,source_url,source_type,region,category,active,scraping_method,requires_selenium,priority,notes
SRC_001,Example Site,https://example.com/events,Website,Toutes Régions,Généraliste,yes,requests,maybe,1,
SRC_002,Facebook Page,https://www.facebook.com/page/,Facebook,Heraklion,Musique,yes,selenium,yes,1,
```

Colonnes :
- **active** : `yes` pour activer la source
- **source_type** : `Website` ou `Facebook`
- **requires_selenium** : `yes`, `no`, ou `maybe`

## Utilisation

### Lancement Rapide

```bash
# Activer l'environnement virtuel
source venv/bin/activate

# Lancer le scraping
./run.sh
```

### Options Avancées

```bash
# Avec options personnalisées
./run.sh --workers 10 --no-cache

# Aide
./run.sh --help
```

Options disponibles :
- `--workers N` : Nombre de workers parallèles (défaut: 5)
- `--no-cache` : Désactiver le cache
- `--no-images` : Ne pas télécharger les images
- `--no-translation` : Ne pas traduire

### Lancement Manuel

```bash
source venv/bin/activate

# Scraping complet
python3 main.py

# Avec options
python3 main.py --workers 10 --no-cache --no-images
```

## Import WordPress

### Prérequis WordPress
1. Installer le plugin **The Events Calendar**
2. Créer un **Application Password** :
   - Utilisateurs → Votre Profil → Application Passwords
   - Créer un nouveau mot de passe pour "Crete Scraper"
   - Copier le mot de passe généré dans `config.json`

### Import

```bash
# Activer l'environnement virtuel
source venv/bin/activate

# Tester la connexion
python3 import_to_wordpress.py --test

# Importer les événements
python3 import_to_wordpress.py data/output/crete_events_20240115.csv

# Import limité (test)
python3 import_to_wordpress.py data/output/crete_events_20240115.csv --limit 10
```

Le script va :
1. Uploader toutes les images dans la médiathèque
2. Créer les événements avec The Events Calendar
3. Associer les images en tant que featured image
4. Créer les catégories et tags automatiquement
5. Utiliser les champs traduits (_fr) pour le contenu

## Structure des Données Exportées

### Colonnes CSV (48 total)

**Colonnes Originales (38)** :
```
event_id, title, subtitle, description, excerpt,
start_date, end_date, all_day, timezone,
venue_name, venue_address, venue_city, venue_region, venue_postal_code, venue_country,
venue_latitude, venue_longitude,
organizer_name, organizer_email, organizer_phone, organizer_website,
category, tags, event_type,
image_url, image_local_path, thumbnail_path, gallery_urls,
price, booking_url, capacity, language,
source_url, source_name, scraped_date, last_updated,
slug, featured, status
```

**Colonnes Traduites (10)** :
```
title_fr, subtitle_fr, description_fr, excerpt_fr,
venue_name_fr, venue_address_fr, venue_city_fr,
organizer_name_fr, category_fr, tags_fr
```

### Format des Dates
- **ISO 8601** : `2024-01-15T20:00:00+02:00`
- **Timezone** : `Europe/Athens` (défaut pour Crète)

### Exemples d'Événements

```json
{
  "event_id": "evt_a1b2c3d4e5f6",
  "title": "Φεστιβάλ Μουσικής Ηρακλείου",
  "title_fr": "Festival de Musique d'Héraklion",
  "description": "Μεγάλο φεστιβάλ με καλλιτέχνες από όλη την Ελλάδα",
  "description_fr": "Grand festival avec des artistes de toute la Grèce",
  "start_date": "2024-07-15T20:00:00+02:00",
  "end_date": "2024-07-15T23:00:00+02:00",
  "venue_name": "Πλατεία Λιοντάρια",
  "venue_name_fr": "Place des Lions",
  "venue_city": "Ηράκλειο",
  "venue_city_fr": "Héraklion",
  "venue_latitude": 35.3387,
  "venue_longitude": 25.1442,
  "category": "Μουσική",
  "category_fr": "Musique",
  "image_url": "https://example.com/image.jpg",
  "image_local_path": "images/events/full/evt_a1b2c3d4e5f6_full.jpg",
  "thumbnail_path": "images/events/thumbnail/evt_a1b2c3d4e5f6_thumb.jpg",
  "source_name": "Crete Events Network",
  "source_url": "https://www.creteevents.gr/"
}
```

## Monitoring & Logs

### Logs

Les logs sont sauvegardés dans `data/logs/` :

```bash
# Voir les logs en temps réel
tail -f data/logs/scraper_20240115.log

# Filtrer les erreurs
grep ERROR data/logs/scraper_20240115.log
```

Niveaux de log :
- **DEBUG** : Détails techniques
- **INFO** : Progression normale
- **WARNING** : Avertissements non-bloquants
- **ERROR** : Erreurs sur sources individuelles
- **CRITICAL** : Erreurs fatales

### Cache

Le cache est stocké dans `data/cache/` :

```bash
# Voir la taille du cache
du -sh data/cache/

# Vider le cache manuellement
rm -rf data/cache/*
```

Le cache est automatiquement nettoyé après 24h (configurable).

### Backups

Les backups JSON sont dans `data/backups/` :

```bash
# Lister les backups
ls -lh data/backups/

# Voir un backup
zcat data/backups/events_backup_20240115.json.gz | jq '.[0]'
```

## Troubleshooting

### Problème : "Chrome driver not found"

**Solution** :
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install chromium-browser

# macOS
brew install --cask google-chrome
```

### Problème : "Facebook login failed"

**Solutions** :
1. Vérifier les credentials dans `config.json`
2. Se connecter manuellement sur Facebook pour résoudre CAPTCHA
3. Supprimer le fichier cookies : `rm cookies/facebook_cookies.pkl`
4. Réessayer le scraping

### Problème : "Translation API rate limit"

**Solution** :
- Augmenter les délais dans `config.json` :
```json
{
  "translation": {
    "batch_size": 5  // Réduire de 10 à 5
  }
}
```

### Problème : "Out of memory"

**Solutions** :
1. Réduire le nombre de workers :
```bash
./run.sh --workers 2
```

2. Désactiver les images temporairement :
```bash
./run.sh --no-images
```

3. Scraper en plusieurs fois (éditer `sources_config_complete.csv`)

### Problème : "WordPress import failed"

**Solutions** :
1. Vérifier la connexion :
```bash
python3 import_to_wordpress.py --test
```

2. Vérifier que The Events Calendar est installé

3. Vérifier les permissions de l'utilisateur WordPress

4. Tester avec un petit échantillon :
```bash
python3 import_to_wordpress.py data/output/events.csv --limit 5
```

## Performance

### Benchmarks Typiques

Sur un serveur moderne (4 cores, 8GB RAM) :

- **Scraping** : ~2-5 minutes pour 202 sources
- **Traduction** : ~10-15 minutes pour 1000 événements
- **Images** : ~5-10 minutes pour 500 images
- **Total** : ~20-30 minutes pour un scraping complet

### Optimisations

1. **Augmenter les workers** (si vous avez plus de RAM) :
```bash
./run.sh --workers 10
```

2. **Utiliser le cache** pour ne scraper que les nouvelles données :
- Le cache évite de re-scraper les sources pendant 24h
- Désactiver seulement si vous voulez forcer un refresh

3. **Scraping sélectif** :
- Éditer `sources_config_complete.csv`
- Mettre `active=no` pour les sources à ignorer

## Sécurité

### Credentials

**IMPORTANT** : Ne jamais committer `config.json` avec vos credentials !

Le fichier est déjà dans `.gitignore`, mais vérifiez :

```bash
# Vérifier que config.json n'est pas tracké
git status

# Si tracké, le retirer
git rm --cached config.json
```

### Bonnes Pratiques

1. **Utiliser des variables d'environnement** (recommandé) :
```bash
export FB_EMAIL="votre@email.com"
export FB_PASSWORD="votre-password"
export WP_USERNAME="username"
export WP_PASSWORD="application-password"
```

2. **Permissions fichiers** :
```bash
chmod 600 config.json  # Lecture/écriture propriétaire seulement
```

3. **Application Passwords WordPress** :
- Ne jamais utiliser votre mot de passe principal
- Créer un Application Password dédié
- Le révoquer si compromis

## Développement

### Structure des Modules

Chaque module a une responsabilité unique :

- **selenium_manager.py** : WebDriver avec anti-détection
- **facebook_scraper.py** : Logique Facebook spécifique
- **web_scraper.py** : Scraping sites web génériques
- **translator.py** : Traduction avec deep-translator
- **image_handler.py** : Download + redimensionnement
- **data_processor.py** : Validation, géolocalisation, dédup
- **csv_exporter.py** : Export CSV formaté
- **cache_manager.py** : Cache disque + retry logic

### Ajouter une Nouvelle Source

1. Éditer `sources_config_complete.csv` :
```csv
SRC_203,Nouveau Site,https://nouveau-site.com/events,Website,Heraklion,Festival,yes,requests,maybe,1,
```

2. Lancer le scraping normalement - la source sera automatiquement incluse

### Contribuer

Les contributions sont bienvenues !

1. Fork le projet
2. Créer une branche feature : `git checkout -b feature/nouvelle-fonctionnalite`
3. Commit : `git commit -am 'Ajout nouvelle fonctionnalité'`
4. Push : `git push origin feature/nouvelle-fonctionnalite`
5. Créer une Pull Request

## Licence

Ce projet est sous licence propriétaire pour Live Crete.

## Support

Pour toute question ou problème :
- Email : livecretemanager@gmail.com
- Issues GitHub : [Créer une issue](https://github.com/votre-repo/issues)

## Changelog

### Version 1.0.0 (2024-01-15)
- 🎉 Release initiale
- ✅ Scraping 202 sources (web + Facebook)
- ✅ Traduction automatique grec/anglais → français
- ✅ Download et redimensionnement images
- ✅ Export CSV 48 colonnes
- ✅ Import WordPress avec The Events Calendar
- ✅ Cache intelligent et retry logic
- ✅ Anti-détection Selenium complet

---

**Développé avec ❤️ pour Live Crete**
