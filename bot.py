import discord
from discord.ext import commands
from google import genai
from google.genai.errors import APIError
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

def generate(prompt):
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

LANG_EMOJIS = {
    "🇺🇸": "American English",
    "🇲🇦": "ⵜⴰⵎⴰⵣⵉⵖⵜ",
    "🇦🇺": "Australian English",
    "🇮🇩": "Bahasa Indonesia",
    "🇲🇾": "Bahasa Melayu",
    "🇬🇧": "British English",
    "🇧🇷": "Português Brasileiro",
    "🇨zechia": "Čeština", # Note corrective mineure pour la clé interne
    "🇩🇰": "Dansk",
    "🇩🇪": "Deutsch",
    "🇪🇸": "Español",
    "🇲🇽": "Español Mexicano",
    "🇫🇷": "Français",
    "🇨🇦": "Français Québécois",
    "🇮🇪": "Gaeilge",
    "🇭🇷": "Hrvatski",
    "🇮🇹": "Italiano",
    "🇬🇱": "Kalaallisut",
    "🇭🇺": "Magyar",
    "🇳🇱": "Nederlands",
    "🇳🇴": "Norsk",
    "🇵🇱": "Polski",
    "🇵🇹": "Português",
    "🇷🇴": "Română",
    "🇫🇮": "Suomi",
    "🇸🇪": "Svenska",
    "🇵🇭": "Tagalog",
    "🇻🇳": "Tiếng Việt",
    "🇹🇷": "Türkçe",
    "🇵🇰": "اردو",
    "🇸🇦": "العربية",
    "🇩🇿": "الدارجة المغربية",
    "🇪🇬": "اللهجة المصرية",
    "🇮🇶": "اللهجة العراقية",
    "🇱🇧": "اللهجة اللبنانية",
    "🇱🇾": "اللهجة الليبية",
    "🇸🇩": "اللهجة السودانية",
    "🇧🇬": "Български",
    "🇷🇸": "Српски",
    "🇺🇦": "Українська",
    "🇷🇺": "Русский",
    "🇵🇸": "עברית",
    "🇮🇷": "فارسي",
    "🇮🇳": "हिन्दी",
    "🇹🇭": "ไทย",
    "🇮🇸": "Íslenska",
    "🇬🇷": "Ελληνικά",
    "🇨🇳": "简体中文",
    "🇯🇵": "日本語",
    "🇰🇷": "한국어"
}

LANG_TO_EMOJI = {v: k for k, v in LANG_EMOJIS.items()}
_all_langs = list(LANG_EMOJIS.items())
_OPTIONS_A = [discord.SelectOption(label=f"{e} {l}", value=e) for e, l in _all_langs[:25]]
_OPTIONS_B = [discord.SelectOption(label=f"{e} {l}", value=e) for e, l in _all_langs[25:]]
_SELECT_A_KEYS = set(e for e, _ in _all_langs[:25])
_SELECT_B_KEYS = set(e for e, _ in _all_langs[25:])

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def process_translation(text: str, target_lang: str | None, mode: str) -> tuple[str, str, str]:
    supported = ", ".join(LANG_EMOJIS.values())
    
    tifinagh_rule = ""
    if target_lang and "ⵜⴰⵎⴰⵣⵉⵖⵜ" in target_lang:
        tifinagh_rule = " CRITICAL FOR TAMAZIGHT: You MUST write the translation exclusively using the Neo-Tifinagh alphabet (ⵜⵉⴼⵉⵏⴰⵖ). Do not use Latin or Arabic characters for this language."

    if mode == "translate" and target_lang:
        prompt = (
            f"Do three things at once:\n"
            f"1. Detect the language of this text from this list ONLY: {supported}. If not in list, write UNKNOWN.\n"
            f"2. Translate the text to {target_lang}. CRITICAL: You MUST write the translation using the native script, alphabet, and writing system of {target_lang}. Do not transliterate into the Roman alphabet.{tifinagh_rule}\n"
            f"3. Provide the phonetic transliteration (Romanization / International Alphabet) of the translated text so a non-native speaker can pronounce it. If {target_lang} already uses the standard Latin alphabet, just repeat the translation exactly.\n\n"
            f"Reply in this exact format (3 lines only):\n"
            f"LANG: <detected language>\n"
            f"RESULT: <translation>\n"
            f"INTER: <international alphabet / romanization>\n\n"
            f"Text: {text}"
        )
    else:
        lang_instruction = f"in {target_lang}" if target_lang else "in the same language as the original text"
        script_instruction = f"using the native script/alphabet of {target_lang}" if target_lang else "using the native script/alphabet of the original text"
        if target_lang and "ⵜⴰⵎⴰⵣⵉⵖⵜ" in target_lang:
            script_instruction = "exclusively using the Neo-Tifinagh alphabet (ⵜⵉⴼⵉⵏⴰⵖ)"
            
        prompt = (
            f"Do two things at once:\n"
            f"1. Detect the language of this text from this list ONLY: {supported}. If not in list, write UNKNOWN.\n"
            f"2. As a humorous Discord bot, reveal the hidden true meaning of this message based on Discord/gaming clichés. Reply {lang_instruction}, short and funny. CRITICAL: You MUST write the result {script_instruction}.\n\n"
            f"Reply in this exact format (2 lines only):\n"
            f"LANG: <detected language>\n"
            f"RESULT: <hidden truth>\n\n"
            f"Text: {text}"
        )

    response_text = generate(prompt)
    lines = response_text.strip().split("\n")
    source_lang = None
    result = ""
    international = ""

    for line in lines:
        if line.startswith("LANG:"):
            raw = line.replace("LANG:", "").strip()
            for lang in LANG_EMOJIS.values():
                if lang.lower() == raw.lower():
                    source_lang = lang
                    break
        elif line.startswith("RESULT:"):
            result = line.replace("RESULT:", "").strip()
        elif line.startswith("INTER:"):
            international = line.replace("INTER:", "").strip()

    return source_lang, result, international


def format_reply_with_emoji(emoji: str, content: str, inter_text: str = "", suffix: str = "", require_inter: bool = False) -> str:
    cleaned_content = content.strip()
    
    inline_test = f"{emoji} {cleaned_content}"
    if "\n" in cleaned_content or len(inline_test) > 40:
        main_body = f"{emoji}\n{cleaned_content}"
    else:
        main_body = inline_test
        
    if require_inter:
        cleaned_inter = inter_text.strip()
        if not cleaned_inter:
            main_body += "\n⚠️ Please, Try Again"
        else:
            inline_inter_test = f"🌐 {cleaned_inter}"
            if len(inline_inter_test) > 40:
                main_body += f"\n🌐\n{cleaned_inter}"
            else:
                main_body += f"\n🌐 {cleaned_inter}"
        
    if suffix:
        return f"{main_body}\n{suffix}"
    return main_body


class TranslateView(discord.ui.View):
    def __init__(self, original_text: str, message_ref: discord.Message, invoker_id: int):
        super().__init__(timeout=120)
        self.original_text = original_text
        self.message_ref = message_ref
        self.invoker_id = invoker_id
        self.selected_values = []

        bt_button = discord.ui.Button(label="Back Thought", style=discord.ButtonStyle.secondary, row=0)
        bt_button.callback = self.bt_callback
        self.add_item(bt_button)

        select_a = discord.ui.Select(placeholder="GROUP A", min_values=1, max_values=1, options=_OPTIONS_A, row=1)
        select_a.callback = self.selecta_callback
        self.add_item(select_a)

        select_b = discord.ui.Select(placeholder="GROUP B", min_values=1, max_values=1, options=_OPTIONS_B, row=2)
        select_b.callback = self.selectb_callback
        self.add_item(select_b)

    def _build_display(self):
        display = []
        if "TRUTH" in self.selected_values:
            display.append("🔎 Reveals the Hidden Truth")
        for v in self.selected_values:
            if v != "TRUTH":
                display.append(f"{v} {LANG_EMOJIS[v]}")
        return ' + '.join(display) if display else None

    def _update_lang(self, new_emoji, from_keys):
        if new_emoji in self.selected_values:
            self.selected_values.remove(new_emoji)
        else:
            prev = [v for v in self.selected_values if v not in from_keys]
            self.selected_values = prev + [new_emoji]

    async def _send_current_state(self, interaction: discord.Interaction):
        display_str = self._build_display()
        short_text = f"*{self.original_text[:80]}{'...' if len(self.original_text) > 80 else ''}*"
        
        # Création de l'embed avec la couleur FF0058
        embed = discord.Embed(title='[ "TRANSLATER". ] *', color=0xFF0058)
        embed.add_field(name="Message :", value=short_text, inline=False)
        
        if display_str is None:
            embed.description = "Please,\nSelect At Least one Option, then Confirm"
        else:
            embed.add_field(name="Selection :", value=display_str, inline=False)
            embed.description = "Confirm"
            
        await interaction.response.edit_message(embed=embed, view=self)

    async def bt_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ This panel does not belong to you.", ephemeral=True)
            return
        if "TRUTH" in self.selected_values:
            self.selected_values.remove("TRUTH")
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.label == "Back Thought":
                    item.style = discord.ButtonStyle.secondary
        else:
            self.selected_values = ["TRUTH"] + [v for v in self.selected_values if v != "TRUTH"]
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.label == "Back Thought":
                    item.style = discord.ButtonStyle.success
                    
        await self._send_current_state(interaction)

    async def selecta_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ This panel does not belong to you.", ephemeral=True)
            return
        self._update_lang(interaction.data["values"][0], _SELECT_A_KEYS)
        await self._send_current_state(interaction)

    async def selectb_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ This panel does not belong to you.", ephemeral=True)
            return
        self._update_lang(interaction.data["values"][0], _SELECT_B_KEYS)
        await self._send_current_state(interaction)

    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.success, row=3)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ This panel does not belong to you.", ephemeral=True)
            return

        if not self.selected_values:
            await interaction.response.send_message("⚠️\nPlease,\nSelect at least one Option first", ephemeral=True)
            return

        await interaction.response.edit_message(content="⏳ Processing . . .", embed=None, view=None)
        self.stop()

        values = self.selected_values
        has_truth = "TRUTH" in values
        lang_values = [v for v in values if v != "TRUTH"]
        translator = interaction.user.mention

        try:
            if not has_truth and len(lang_values) == 1:
                target_lang = LANG_EMOJIS[lang_values[0]]
                source_lang, result_text, inter_text = process_translation(self.original_text, target_lang, "translate")

                if source_lang is None:
                    await interaction.followup.send("❌ ERROR", ephemeral=True)
                    await interaction.followup.send("Language Not Enregistered", ephemeral=True)
                    return

                source_emoji = LANG_TO_EMOJI.get(source_lang, "🏳️")
                if source_lang == target_lang:
                    reply = format_reply_with_emoji(source_emoji, f"*(Already in {source_lang}.)*", suffix=translator, require_inter=False)
                else:
                    reply = format_reply_with_emoji(source_emoji, result_text, inter_text=inter_text, suffix=f"Translated by {translator}", require_inter=True)

            elif has_truth and len(lang_values) == 0:
                source_lang, result_text, _ = process_translation(self.original_text, None, "truth")

                if source_lang is None:
                    await interaction.followup.send("❌ ERROR", ephemeral=True)
                    await interaction.followup.send("Language Not Enregistered", ephemeral=True)
                    return

                reply = f"{result_text}\nRevealed by {translator}"

            elif has_truth and len(lang_values) == 1:
                target_lang = LANG_EMOJIS[lang_values[0]]
                source_lang, truth_text, _ = process_translation(self.original_text, None, "truth")

                if source_lang is None:
                    await interaction.followup.send("❌ ERROR", ephemeral=True)
                    await interaction.followup.send("Language Not Enregistered", ephemeral=True)
                    return

                source_emoji = LANG_TO_EMOJI.get(source_lang, "🏳️")

                if source_lang == target_lang:
                    combined_text = f"*(Already in {target_lang}.)*\n\n{truth_text}"
                    reply = format_reply_with_emoji(source_emoji, combined_text, suffix=f"Revealed by {translator}", require_inter=False)
                else:
                    _, translated_truth, inter_text = process_translation(truth_text, target_lang, "translate")
                    reply = format_reply_with_emoji(source_emoji, translated_truth, inter_text=inter_text, suffix=f"Revealed and Translated by {translator}", require_inter=True)

            else:
                await interaction.followup.send("❌ ERROR", ephemeral=True)
                await interaction.followup.send("Invalid Combination", ephemeral=True)
                return

            await self.message_ref.reply(reply)
            await interaction.edit_original_response(content="DONE ! ✅")

        except APIError as api_err:
            if api_err.code == 429 or "RESOURCE_EXHAUSTED" in str(api_err):
                await interaction.followup.send("❌ ERROR", ephemeral=True)
                await interaction.followup.send("⚠️\nYour Plan Limit has been Reached", ephemeral=True)
                try:
                    await interaction.edit_original_response(content="❌ ERROR")
                except Exception:
                    pass
                return

            await interaction.followup.send("❌ ERROR", ephemeral=True)
            await interaction.followup.send("⚠️\nPlease,\nTry Again", ephemeral=True)
            try:
                await interaction.edit_original_response(content="❌ ERROR")
            except Exception:
                pass

        except Exception as e:
            await interaction.followup.send("❌ ERROR", ephemeral=True)
            await interaction.followup.send("⚠️\nPlease,\nTry Again", ephemeral=True)
            try:
                await interaction.edit_original_response(content="❌ ERROR")
            except Exception:
                pass

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger, row=3)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message("❌ This panel does not belong to you.", ephemeral=True)
            return
        
        await interaction.response.edit_message(content="DONE ! ✅", embed=None, view=None)
        await interaction.followup.send("❌ Cancelled", ephemeral=True)
        self.stop()


@bot.tree.context_menu(name="TRANSLATER")
async def translate_context_menu(interaction: discord.Interaction, message: discord.Message):
    if not message.content.strip():
        await interaction.response.send_message("❌ This Message is Not Compatible with the Application [ \"TRANSLATER\". ] *", ephemeral=True)
        return

    view = TranslateView(original_text=message.content, message_ref=message, invoker_id=interaction.user.id)
    
    # Création de l'embed initial avec la couleur FF0058
    short_text = f"*{message.content[:80]}{'...' if len(message.content) > 80 else ''}*"
    embed = discord.Embed(title='[ "TRANSLATER". ] *', color=0xFF0058)
    embed.add_field(name="Message :", value=short_text, inline=False)
    embed.description = "Please,\nSelect At Least one Option, then Confirm"

    await interaction.response.send_message(
        embed=embed,
        view=view,
        ephemeral=True
    )


@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        print("✅ Command(s) synced")
    except Exception as e:
        print(f"❌ Sync error: {e}")
    print(f"✅ Bot connected: {bot.user}")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
            
