DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = {"it", "en"}

MESSAGES = {
    "it": {
        # events
        "takeoff":          "✈️ {name} è decollato\n{alt}m AMSL  {speed}km/h\n{loc}",
        "landing":          "\U0001f6ec {name} è atterrato\n{note}\n{loc}",
        "bad_air":          "⚠️ {name} — aria brutta\n{note}\n{loc}",
        "bad_landing":      "\U0001f198 {name} — atterraggio duro\n{note}\n{loc}",
        "reserve":          "\U0001f6a8 {name} — POSSIBILE RISERVA\n{note}\n{loc}",
        "impact":           "\U0001f6a8 {name} — POSSIBILE IMPATTO\n{note}\n{loc}",
        "in_orbita":        "\U0001f680 {name} è in orbita\n{note}\n{loc}",
        "piange_giallo":    "\U0001f605 {name} piange giallo\n{note}\n{loc}",
        "ha_fatto_strada":  "\U0001f5fa️ {name} ha fatto strada\n{note}\n{loc}",
        "climbing_well":    "\U0001f4c8 {name} in buon lift\n{note}\n{loc}",
        "signal_lost":      "\U0001f4f5 {name} — segnale perso\n{note}",
        "signal_found":     "\U0001f4f6 {name} — segnale ritrovato\n{loc}",
        # bot UI
        "status_header":    "✈️ *Stato piloti*",
        "no_data":          "Nessun dato ricevuto.",
        "airborne_since":   "In volo da: {min} min",
        "age_live":         "live",
        "age_min":          "{min}min fa",
        "lang_set":         "Lingua impostata: italiano \U0001f1ee\U0001f1f9",
        "lang_unknown":     "Lingua non supportata. Usa: {langs}",
    },
    "en": {
        # events
        "takeoff":          "✈️ {name} took off\n{alt}m AMSL  {speed}km/h\n{loc}",
        "landing":          "\U0001f6ec {name} landed\n{note}\n{loc}",
        "bad_air":          "⚠️ {name} — rough air\n{note}\n{loc}",
        "bad_landing":      "\U0001f198 {name} — hard landing\n{note}\n{loc}",
        "reserve":          "\U0001f6a8 {name} — POSSIBLE RESERVE\n{note}\n{loc}",
        "impact":           "\U0001f6a8 {name} — POSSIBLE IMPACT\n{note}\n{loc}",
        "in_orbita":        "\U0001f680 {name} is soaring high\n{note}\n{loc}",
        "piange_giallo":    "\U0001f605 {name} has been flying 4+ hours\n{note}\n{loc}",
        "ha_fatto_strada":  "\U0001f5fa️ {name} has covered some distance\n{note}\n{loc}",
        "climbing_well":    "\U0001f4c8 {name} climbing well\n{note}\n{loc}",
        "signal_lost":      "\U0001f4f5 {name} — signal lost\n{note}",
        "signal_found":     "\U0001f4f6 {name} — signal found\n{loc}",
        # bot UI
        "status_header":    "✈️ *Pilots status*",
        "no_data":          "No data received.",
        "airborne_since":   "Airborne for: {min} min",
        "age_live":         "live",
        "age_min":          "{min}min ago",
        "lang_set":         "Language set: English \U0001f1ec\U0001f1e7",
        "lang_unknown":     "Unsupported language. Use: {langs}",
    },
}
