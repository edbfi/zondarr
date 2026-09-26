<script lang="ts">
/**
 * Success page component for completed registration.
 *
 * Displays:
 * - Success message with checkmark
 * - Server access instructions
 * - List of created user accounts
 *
 * @module $lib/components/join/success-page
 */

import { CheckCircle, ExternalLink, Server, User } from '@lucide/svelte';
import type { RedemptionResponse } from '$lib/api/client';
import { Button } from '$lib/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '$lib/components/ui/card';

interface Props {
	response: RedemptionResponse;
	hasPlexServer?: boolean;
}

const { response, hasPlexServer = false }: Props = $props();
</script>

<div class="space-y-6" data-success-page>
	<!-- Success Header -->
	<Card class="border-emerald-500/30 bg-emerald-500/5">
		<CardHeader>
			<div class="flex items-center gap-3">
				<div class="rounded-full bg-emerald-500/15 p-3 text-emerald-400">
					<CheckCircle class="size-8" />
				</div>
				<div>
					<CardTitle class="text-cr-text text-xl">Account Created Successfully!</CardTitle>
					<CardDescription class="text-cr-text-muted">
						{response.message ?? 'Your media server account has been created.'}
					</CardDescription>
				</div>
			</div>
		</CardHeader>
	</Card>

	<!-- Created Accounts -->
	{#if response.users_created && response.users_created.length > 0}
		<Card class="border-cr-border bg-cr-surface">
			<CardHeader>
				<div class="flex items-center gap-2">
					<User class="size-5 text-cr-accent" />
					<CardTitle class="text-cr-text">Your Accounts</CardTitle>
				</div>
				<CardDescription class="text-cr-text-muted">
					You can now access the following servers with your credentials.
				</CardDescription>
			</CardHeader>
			<CardContent class="space-y-3">
				{#each response.users_created as user (user.id)}
					<div
						class="flex items-center gap-3 rounded-lg border border-cr-border bg-cr-bg p-4"
						data-created-user={user.id}
					>
						<div class="rounded-full bg-cr-accent/15 p-2 text-cr-accent">
							<Server class="size-4" />
						</div>
						<div>
							<p class="font-medium text-cr-text">{user.username}</p>
							<p class="text-sm text-cr-text-muted font-mono">{user.external_user_id}</p>
						</div>
					</div>
				{/each}
				{#if hasPlexServer}
					<Button
						variant="outline"
						class="w-full border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
						onclick={() => window.open('https://app.plex.tv', '_blank')}
					>
						<ExternalLink class="size-4 mr-2" />
						Open Plex
					</Button>
				{/if}
			</CardContent>
		</Card>
	{/if}

	<!-- Instructions -->
	<Card class="border-cr-border bg-cr-surface">
		<CardHeader>
			<CardTitle class="text-cr-text">What's Next?</CardTitle>
		</CardHeader>
		<CardContent class="space-y-4">
			<div class="flex items-start gap-3">
				<div
					class="flex size-6 shrink-0 items-center justify-center rounded-full bg-cr-accent/15 text-cr-accent text-sm font-medium"
				>
					1
				</div>
				<div>
					<p class="font-medium text-cr-text">Download a Media Player</p>
					<p class="text-sm text-cr-text-muted">
						Install a compatible media player app on your device.
					</p>
				</div>
			</div>
			<div class="flex items-start gap-3">
				<div
					class="flex size-6 shrink-0 items-center justify-center rounded-full bg-cr-accent/15 text-cr-accent text-sm font-medium"
				>
					2
				</div>
				<div>
					<p class="font-medium text-cr-text">Connect to the Server</p>
					<p class="text-sm text-cr-text-muted">Enter the server URL when prompted in the app.</p>
				</div>
			</div>
			<div class="flex items-start gap-3">
				<div
					class="flex size-6 shrink-0 items-center justify-center rounded-full bg-cr-accent/15 text-cr-accent text-sm font-medium"
				>
					3
				</div>
				<div>
					<p class="font-medium text-cr-text">Sign In</p>
					<p class="text-sm text-cr-text-muted">
						Use the username and password you just created to sign in.
					</p>
				</div>
			</div>
		</CardContent>
	</Card>
</div>
