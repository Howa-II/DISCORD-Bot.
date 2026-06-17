import discord
from discord.ext import commands
import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─── Langue registry ──────────────────────────────────────────────────────────

LANG_EMOJIS = {
    "🇬🇧": "anglais",
    "🇫🇷": "français",
    "🇸🇦": "arabe",
    "🇯🇵": "japonais",
    "🇮🇹": "italien",
    "🇩🇪": "allemand",
    "🇪🇸": "espagnol",
    "🇷🇺": "russe",
    "🇲🇦": "darija marocain",
}

TRUTH_EMOJI = "🔎"
CANCEL_EMOJI = "❌"
CONFIRM_EMOJI = "✅"

# Mapping langue → émoji (pour la réponse)
LANG_TO_EMOJI = {v: k for k, v in LANG_EMOJIS.items()}

# ─── Bot setup ────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Sessions actives : message_id → {"emojis": set(), "author": user_id}
active_sessions: dict[int, dict] = {}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def detect_language(text: str) -> str | None:
    """Demande à Claude de détecter la langue du message. Retourne le nom de la langue ou None si non enregistrée."""
    supported = ", ".join(LANG_EMOJIS.values())
    prompt = (
        f"Détecte la langue du texte suivant. "
        f"Réponds UNIQUEMENT avec le nom exact de la langue parmi cette liste : {supported}. "
        f"Si la langue n'est PAS dans cette liste, réponds uniquement avec le mot : INCONNU.\n\n"
        f"Texte : {text}"
    )
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=20,
        messages=[{"role": "user", "content": prompt}]
    )
    result = response.content[0].text.strip().lower()
    # Vérifier si c'est une langue connue
    for lang in LANG_EMOJIS.values():
        if lang.lower() == result:
            return lang
    return None  # INCONNU


def translate_text(text: str, target_lang: str) -> str:
    """Traduit le texte dans la langue cible via Claude."""
    prompt = (
        f"Traduis le texte suivant en {target_lang}. "
        f"Réponds UNIQUEMENT avec la traduction, sans explication ni ponctuation supplémentaire.\n\n"
        f"Texte : {text}"
    )
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def get_truth(text: str, target_lang: str | None = None) -> str:
    """Génère la 'vérité cachée' Discord du message. Si target_lang est fourni, répond dans cette langue."""
    lang_instruction = f"en {target_lang}" if target_lang else "dans la même langue que le message original"
    prompt = (
        f"Tu es un bot Discord humoristique. "
        f"Révèle la 'vraie signification' cachée derrière ce message, "
        f"en te basant sur les clichés et l'humour Discord (gaming, procrastination, excuses, etc.). "
        f"Réponds {lang_instruction}, de façon courte et drôle, SANS explication. "
        f"Réponds UNIQUEMENT avec la vérité cachée.\n\n"
        f"Message : {text}"
    )
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def validate_combo(emojis: set) -> tuple[bool, str]:
    """
    Valide la combinaison d'émojis sélectionnés.
    Retourne (is_valid, error_message).
    Combos valides :
      - 1 emoji langue seul → traduction
      - 🔎 seul → vérité dans langue source
      - 🔎 + 1 emoji langue → vérité traduite dans la langue choisie
    """
    lang_emojis_selected = emojis & set(LANG_EMOJIS.keys())
    has_truth = TRUTH_EMOJI in emojis
    n_langs = len(lang_emojis_selected)
    n_total = len(emojis)

    # Cas invalides
    if n_total == 0:
        return False, "⚠️ Aucun émoji sélectionné."

    if n_langs > 1:
        return False, (
            f"❌ **Combinaison incompatible** : tu as sélectionné {n_langs} langues "
            f"({' '.join(lang_emojis_selected)}). Choisis-en une seule."
        )

    if has_truth and emojis.count if hasattr(emojis, 'count') else list(emojis).count(TRUTH_EMOJI) > 1:
        return False, "❌ **Combinaison incompatible** : tu ne peux pas utiliser 🔎 deux fois."

    # Combos valides possibles :
    # {lang}  → OK
    # {🔎}    → OK
    # {lang, 🔎} → OK
    # Tout le reste → KO

    if n_total == 1 and n_langs == 1:
        return True, ""  # traduction simple

    if n_total == 1 and has_truth:
        return True, ""  # vérité en langue source

    if n_total == 2 and n_langs == 1 and has_truth:
        return True, ""  # vérité traduite

    return False, (
        f"❌ **Combinaison incompatible** : `{''.join(emojis)}` n'est pas une combinaison valide. "
        f"Utilise : une langue seule, 🔎 seul, ou 🔎 + une langue."
    )

# ─── Commande contextuelle (clic droit → Apps) ────────────────────────────────

@bot.tree.context_menu(name="🌍 Traduire / Vérité")
async def translate_context_menu(interaction: discord.Interaction, message: discord.Message):
    """Lance la session de sélection d'émojis sur un message."""
    # Si une session est déjà active sur ce message
    if message.id in active_sessions:
        await interaction.response.send_message(
            "⏳ Une session est déjà en cours sur ce message.", ephemeral=True
        )
        return

    active_sessions[message.id] = {
        "emojis": set(),
        "author_id": interaction.user.id,
        "original_text": message.content,
        "channel_id": interaction.channel_id,
        "message_ref": message,
    }

    # Construire le panneau de sélection
    lang_list = " | ".join([f"{e} {l.capitalize()}" for e, l in LANG_EMOJIS.items()])
    panel = (
        f"## 🌍 Sélection pour le message de {message.author.mention}\n"
        f"**Message :** *{message.content[:100]}{'...' if len(message.content) > 100 else ''}*\n\n"
        f"**Langues disponibles :**\n{lang_list} | {TRUTH_EMOJI} Vérité\n\n"
        f"Clique sur les boutons ci-dessous pour sélectionner tes émojis, puis confirme avec ✅."
    )

    view = EmojiSelectorView(message_id=message.id, invoker_id=interaction.user.id)
    await interaction.response.send_message(panel, view=view, ephemeral=True)


# ─── Vue de sélection d'émojis ────────────────────────────────────────────────

class EmojiSelectorView(discord.ui.View):
    def __init__(self, message_id: int, invoker_id: int):
        super().__init__(timeout=60)
        self.message_id = message_id
        self.invoker_id = invoker_id

        # Ajouter les boutons de langue
        for emoji in LANG_EMOJIS:
            self.add_item(EmojiToggleButton(emoji=emoji, message_id=message_id, invoker_id=invoker_id))

        # Bouton vérité
        self.add_item(EmojiToggleButton(emoji=TRUTH_EMOJI, message_id=message_id, invoker_id=invoker_id))

        # Boutons Confirmer / Annuler
        self.add_item(ConfirmButton(message_id=message_id, invoker_id=invoker_id))
        self.add_item(CancelButton(message_id=message_id, invoker_id=invoker_id))

    async def on_timeout(self):
        active_sessions.pop(self.message_id, None)


class EmojiToggleButton(discord.ui.Button):
    def __init__(self, emoji: str, message_id: int, invoker_id: int):
        super().__init__(style=discord.ButtonStyle.secondary, emoji=emoji, row=self._get_row(emoji))
        self.message_id = message_id
        self.invoker_id = invoker_id

    def _get_row(self, emoji: str) -> int:
        all_emojis = list(LANG_EMOJIS.keys()) + [TRUTH_EMOJI]
        idx = all_emojis.index(emoji) if emoji in all_emojis else 0
        return idx // 5  # 5 boutons par ligne, max 3 lignes

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ Ce panneau ne t'appartient pas.", ephemeral=True)
            return

        session = active_sessions.get(self.message_id)
        if not session:
            await interaction.response.send_message("❌ Session expirée.", ephemeral=True)
            return

        emoji = str(self.emoji)
        if emoji in session["emojis"]:
            session["emojis"].discard(emoji)
            self.style = discord.ButtonStyle.secondary
        else:
            session["emojis"].add(emoji)
            self.style = discord.ButtonStyle.primary

        selected = " ".join(session["emojis"]) if session["emojis"] else "*(aucun)*"
        await interaction.response.edit_message(
            content=(
                interaction.message.content.split("\n\n**Sélection actuelle")[0]
                + f"\n\n**Sélection actuelle :** {selected}"
            ),
            view=self.view
        )


class ConfirmButton(discord.ui.Button):
    def __init__(self, message_id: int, invoker_id: int):
        super().__init__(style=discord.ButtonStyle.success, label="✅ Confirmer", row=3)
        self.message_id = message_id
        self.invoker_id = invoker_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ Ce panneau ne t'appartient pas.", ephemeral=True)
            return

        session = active_sessions.pop(self.message_id, None)
        if not session:
            await interaction.response.send_message("❌ Session expirée.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        emojis = session["emojis"]
        text = session["original_text"]
        original_message = session["message_ref"]
        channel = bot.get_channel(session["channel_id"])

        # Valider la combinaison
        is_valid, error_msg = validate_combo(emojis)
        if not is_valid:
            await interaction.followup.send(error_msg, ephemeral=True)
            return

        # Détecter la langue source
        source_lang = detect_language(text)
        if source_lang is None:
            await interaction.followup.send(
                f"❌ **Langue non enregistrée** : la langue du message n'est pas dans ma liste "
                f"({', '.join(LANG_EMOJIS.values())}). Je ne peux pas traiter ce message.",
                ephemeral=True
            )
            return

        source_emoji = LANG_TO_EMOJI.get(source_lang, "🏳️")

        lang_selected = emojis & set(LANG_EMOJIS.keys())
        has_truth = TRUTH_EMOJI in emojis

        # ── Cas 1 : Traduction simple (1 langue seule) ──
        if len(emojis) == 1 and lang_selected:
            target_emoji = list(lang_selected)[0]
            target_lang = LANG_EMOJIS[target_emoji]

            # Même langue source = cible → inutile
            if target_lang == source_lang:
                result = f"{source_emoji} *(Le message est déjà en {source_lang}.)*"
            else:
                translated = translate_text(text, target_lang)
                result = f"{source_emoji} {translated}"

            await original_message.reply(result)

        # ── Cas 2 : Vérité seule (🔎) ──
        elif len(emojis) == 1 and has_truth:
            truth = get_truth(text, target_lang=None)
            result = f"{source_emoji} 🔎 {truth}"
            await original_message.reply(result)

        # ── Cas 3 : Vérité + langue (🔎 + lang) ──
        elif len(emojis) == 2 and lang_selected and has_truth:
            target_emoji = list(lang_selected)[0]
            target_lang = LANG_EMOJIS[target_emoji]
            truth = get_truth(text, target_lang=target_lang)
            result = f"{source_emoji} 🔎 {truth}"
            await original_message.reply(result)

        await interaction.followup.send("✅ Traitement terminé !", ephemeral=True)
        self.view.stop()


class CancelButton(discord.ui.Button):
    def __init__(self, message_id: int, invoker_id: int):
        super().__init__(style=discord.ButtonStyle.danger, label="❌ Annuler", row=3)
        self.message_id = message_id
        self.invoker_id = invoker_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ Ce panneau ne t'appartient pas.", ephemeral=True)
            return

        active_sessions.pop(self.message_id, None)
        await interaction.response.edit_message(content="❌ Session annulée.", view=None)
        self.view.stop()


# ─── Events ───────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot connecté en tant que {bot.user} (ID: {bot.user.id})")
    print(f"   Langues supportées : {', '.join(LANG_EMOJIS.values())}")


# ─── Lancement ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
  
