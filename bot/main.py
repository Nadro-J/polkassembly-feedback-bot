import discord
from discord import app_commands
from utils.async_data_handler import AsyncDataHandler
from utils.config import *

intents = discord.Intents.default()
intents.message_content = True

server_id = discord.Object(id=GUILD_ID)
forum_channel_id = FORUM_CHANNEL
signatory_role_id = SIGNATORY_ROLE
signatory_threshold = REACTION_THRESHOLD
approval_emoji = APPROVAL_EMOJI
reject_emoji = REJECTION_EMOJI


class FeedbackClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store and work with them.
        # Note: When using commands.Bot instead of discord.Client, the bot will
        # maintain its own tree instead.
        self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global commands instead.
    # By doing so, we don't have to wait up to an hour until they are shown to the end-user.
    async def setup_hook(self):
        # This copies the global commands over to your guild.
        self.tree.copy_global_to(guild=server_id)
        await self.tree.sync(guild=server_id)


intents = discord.Intents.default()
intents.members = True
client = FeedbackClient(intents=intents)


class FeedbackForm(discord.ui.Modal, title='Feedback Form'):
    referendum = discord.ui.TextInput(label='Referendum', placeholder='Enter the referendum number', required=True)
    context = discord.ui.TextInput(label='Context', style=discord.TextStyle.paragraph, placeholder='Enter context here',
                                   required=True)

    async def on_submit(self, interaction: discord.Interaction):
        # Get the feedback channel
        feedback_data = AsyncDataHandler('../feedback.json')
        feedback_channel = interaction.guild.get_channel(forum_channel_id)
        role = discord.utils.get(interaction.guild.roles, id=signatory_role_id)

        if feedback_channel:
            # Post the feedback to the channel
            thumbnail = discord.File('./media/polkassembly.png')
            embed = discord.Embed(title="Feedback Submitted (Pending approval)", description=self.context.value,
                                  timestamp=interaction.created_at)
            embed.set_thumbnail(url='attachment://polkassembly.png')
            embed.set_author(name=f"Referendum #{self.referendum.value}",
                             url=f"https://polkadot.polkassembly.io/referenda/{self.referendum.value}")
            embed.add_field(name=approval_emoji, value=0, inline=True)
            embed.add_field(name=reject_emoji, value=0, inline=True)
            embed.add_field(name="signatories", value="", inline=False)
            embed.set_footer(text=f"{signatory_threshold} reactions are required to either approve or reject the request")

            feedback_message = await interaction.channel.send(content=role.mention, file=thumbnail, embed=embed)

            await feedback_message.add_reaction(approval_emoji)
            await feedback_message.add_reaction(reject_emoji)

            await interaction.response.send_message('Your feedback has been submitted!', ephemeral=True)
            await feedback_data.record(discord_message_id=feedback_message.id, context=self.context.value,
                                       index=self.referendum.value, status='awaiting decision',
                                       created_by_usr=interaction.user.name, created_by_uid=interaction.user.id)


@client.event
async def on_ready():
    print(f'Logged in as {client.user}!')


@client.tree.command(name="post-feedback", description="Submit feedback")
@app_commands.checks.has_role(signatory_role_id)
async def post_feedback(interaction: discord.Interaction):
    await interaction.response.send_modal(FeedbackForm())


@post_feedback.error
async def post_feedback_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingRole):
        role = discord.utils.get(interaction.guild.roles, id=signatory_role_id)
        await interaction.response.send_message(
            f'You are required to have {role.mention} to be able to submit feedback!', ephemeral=True)


@client.event
async def on_raw_reaction_add(reaction: discord.RawReactionActionEvent):
    active_threads = [thread.id for thread in client.get_channel(forum_channel_id).threads]

    if reaction.channel_id not in active_threads:
        return

    guild = client.get_guild(reaction.guild_id)
    forum = guild.get_channel(forum_channel_id)
    thread = forum.get_thread(reaction.channel_id)
    message = await thread.fetch_message(reaction.message_id)

    await approved_or_reject(message=message, reaction=reaction, guild=guild)


async def approved_or_reject(message, reaction, guild):
    feedback_data = AsyncDataHandler('../feedback.json')

    already_signed = await feedback_data.get_signatories(discord_message_id=message.id)
    if already_signed is not False and str(reaction.member.id) in already_signed:
        return


    total_approved = await feedback_data.get_total_approved_or_rejected(discord_message_id=message.id,
                                                                        vote_type="approved")
    total_rejected = await feedback_data.get_total_approved_or_rejected(discord_message_id=message.id,
                                                                        vote_type="rejected")

    if str(reaction.emoji) == approval_emoji:
        role = discord.utils.get(guild.roles, id=signatory_role_id)
        user = reaction.member.display_name

        if "Rejected" in message.embeds[0].title or "Approved" in message.embeds[0].title:
            return

        if role in guild.get_member(reaction.member.id).roles and "Feedback" in message.embeds[0].title:
            approval_reaction = discord.utils.get(message.reactions, emoji=approval_emoji)

            if approval_reaction and total_approved >= signatory_threshold:
                # Define the action to be taken when the reaction threshold is met
                message.embeds[0].title = "Feedback Submitted (Approved)"
                message.embeds[0].set_thumbnail(url='attachment://polkassembly.png')
                message.embeds[0].set_field_at(index=0, name=approval_emoji, value=total_approved + 1)

                new_value = message.embeds[0].fields[2].value + "\n" + user + " " + approval_emoji
                message.embeds[0].set_field_at(index=2, name='signatories', value=new_value, inline=False)
                await message.edit(embed=message.embeds[0])
                await feedback_data.add_signatory(discord_message_id=message.id, user_id=reaction.member.id,
                                                  username=reaction.member.name, decision=approval_emoji)

                await message.edit(embed=message.embeds[0])
                await message.channel.send(
                    f"The message has reached the threshold of {signatory_threshold} {approval_emoji} reactions!")
                await feedback_data.update(discord_message_id=message.id, status='approved')
            else:
                await feedback_data.update(discord_message_id=message.id, approved=total_approved + 1)
                message.embeds[0].set_thumbnail(url='attachment://polkassembly.png')
                message.embeds[0].set_field_at(index=0, name=approval_emoji, value=total_approved + 1)

                new_value = message.embeds[0].fields[2].value + "\n" + user + " " + approval_emoji
                message.embeds[0].set_field_at(index=2, name='signatories', value=new_value, inline=False)
                await message.edit(embed=message.embeds[0])
                await feedback_data.add_signatory(discord_message_id=message.id, user_id=reaction.member.id,
                                                  username=reaction.member.name, decision=approval_emoji)

    if str(reaction.emoji) == reject_emoji:
        role = discord.utils.get(guild.roles, id=signatory_role_id)
        user = reaction.member.display_name

        if "Rejected" in message.embeds[0].title or "Approved" in message.embeds[0].title:
            return

        if role in guild.get_member(reaction.member.id).roles and "Feedback" in message.embeds[0].title:
            rejection_reaction = discord.utils.get(message.reactions, emoji=reject_emoji)

            if rejection_reaction and total_rejected >= signatory_threshold:
                # Define the action to be taken when the reaction threshold is met
                message.embeds[0].title = "Feedback Submitted (Rejected)"
                await feedback_data.update(discord_message_id=message.id, rejected=total_rejected + 1)
                message.embeds[0].set_thumbnail(url='attachment://polkassembly.png')
                message.embeds[0].set_field_at(index=1, name=reject_emoji, value=total_rejected + 1)

                new_value = message.embeds[0].fields[2].value + "\n" + user + " " + reject_emoji
                message.embeds[0].set_field_at(index=2, name='signatories', value=new_value, inline=False)
                await message.edit(embed=message.embeds[0])
                await feedback_data.add_signatory(discord_message_id=message.id, user_id=reaction.member.id,
                                                  username=reaction.member.name, decision=reject_emoji)

                await message.edit(embed=message.embeds[0])
                await message.channel.send(
                    f"This message has been rejected {signatory_threshold} {reject_emoji} reactions!")
                await feedback_data.update(discord_message_id=message.id, status='rejected')  # in-progress
            else:

                await feedback_data.update(discord_message_id=message.id, rejected=total_rejected + 1)
                message.embeds[0].set_thumbnail(url='attachment://polkassembly.png')
                message.embeds[0].set_field_at(index=1, name=reject_emoji, value=total_rejected + 1)

                new_value = message.embeds[0].fields[2].value + "\n" + user + " " + reject_emoji
                message.embeds[0].set_field_at(index=2, name='signatories', value=new_value, inline=False)
                await message.edit(embed=message.embeds[0])
                await feedback_data.add_signatory(discord_message_id=message.id, user_id=reaction.member.id,
                                                  username=reaction.member.name, decision=reject_emoji)


if __name__ == '__main__':
    client.run(token=CLIENT_SECRET, reconnect=True)
