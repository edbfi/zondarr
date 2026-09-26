<script lang="ts">
import { KeyRound, User } from '@lucide/svelte';
import { type AdminMeResponse, changePassword, updateAdminEmail } from '$lib/api/auth';
import LinkProviderCard from '$lib/components/settings/link-provider-card.svelte';
import TotpManagementCard from '$lib/components/settings/totp-management-card.svelte';
import { Badge } from '$lib/components/ui/badge';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import { emailUpdateSchema, passwordChangeSchema } from '$lib/schemas/settings';
import { showApiError, showError, showSuccess } from '$lib/utils/toast';

interface Props {
	me: AdminMeResponse;
}

let { me }: Props = $props();

// TOTP state — intentionally captures initial prop value for local editing
// svelte-ignore state_referenced_locally
let totpEnabled = $state(me.totp_enabled ?? false);

// Email state — intentionally captures initial prop value for local editing
// svelte-ignore state_referenced_locally
let email = $state(me.email ?? '');
let savingEmail = $state(false);

// Password state
let currentPassword = $state('');
let newPassword = $state('');
let confirmPassword = $state('');
let changingPassword = $state(false);

async function handleEmailSave() {
	const parsed = emailUpdateSchema.safeParse({ email });
	if (!parsed.success) {
		showError(parsed.error.issues[0]?.message ?? 'Invalid email');
		return;
	}

	savingEmail = true;
	try {
		const result = await updateAdminEmail({ email: parsed.data.email });
		if (result.error) {
			showApiError(result.error);
		} else {
			showSuccess('Email updated');
		}
	} finally {
		savingEmail = false;
	}
}

async function handlePasswordChange() {
	const parsed = passwordChangeSchema.safeParse({
		current_password: currentPassword,
		new_password: newPassword,
		confirm_password: confirmPassword
	});
	if (!parsed.success) {
		showError(parsed.error.issues[0]?.message ?? 'Invalid input');
		return;
	}

	changingPassword = true;
	try {
		const result = await changePassword({
			current_password: currentPassword,
			new_password: newPassword
		});
		if (result.error) {
			showApiError(result.error);
		} else {
			showSuccess('Password changed successfully');
			currentPassword = '';
			newPassword = '';
			confirmPassword = '';
		}
	} finally {
		changingPassword = false;
	}
}
</script>

<div class="space-y-6">
	<!-- Profile Card -->
	<Card.Root>
		<Card.Header>
			<div class="flex items-center gap-2">
				<User class="size-5 text-cr-accent" />
				<Card.Title>Profile</Card.Title>
			</div>
			<Card.Description>Your admin account details.</Card.Description>
		</Card.Header>
		<Card.Content>
			<div class="space-y-4">
				<div class="space-y-2">
					<Label>Username</Label>
					<Input value={me.username} disabled />
				</div>
				<div class="space-y-2">
					<Label>Auth Method</Label>
					<div>
						<Badge variant="outline">{me.auth_method}</Badge>
					</div>
				</div>
				<div class="space-y-2">
					<Label for="admin-email">Email</Label>
					<Input id="admin-email" type="email" placeholder="admin@example.com" bind:value={email} />
				</div>
				<Button onclick={handleEmailSave} disabled={savingEmail}>
					{savingEmail ? 'Saving...' : 'Save Email'}
				</Button>
			</div>
		</Card.Content>
	</Card.Root>

	<!-- Link Provider Card -->
	<LinkProviderCard authMethod={me.auth_method} />

	<!-- Password Card (only for local auth) -->
	{#if me.auth_method === 'local'}
		<Card.Root>
			<Card.Header>
				<div class="flex items-center gap-2">
					<KeyRound class="size-5 text-cr-accent" />
					<Card.Title>Change Password</Card.Title>
				</div>
				<Card.Description>Update your login password. Minimum 15 characters.</Card.Description>
			</Card.Header>
			<Card.Content>
				<div class="space-y-4">
					<div class="space-y-2">
						<Label for="current-password">Current Password</Label>
						<Input
							id="current-password"
							type="password"
							bind:value={currentPassword}
							autocomplete="current-password"
						/>
					</div>
					<div class="space-y-2">
						<Label for="new-password">New Password</Label>
						<Input
							id="new-password"
							type="password"
							bind:value={newPassword}
							autocomplete="new-password"
						/>
					</div>
					<div class="space-y-2">
						<Label for="confirm-password">Confirm New Password</Label>
						<Input
							id="confirm-password"
							type="password"
							bind:value={confirmPassword}
							autocomplete="new-password"
						/>
					</div>
					<Button onclick={handlePasswordChange} disabled={changingPassword}>
						{changingPassword ? 'Changing...' : 'Change Password'}
					</Button>
				</div>
			</Card.Content>
		</Card.Root>

		<!-- Two-Factor Authentication Card -->
		<TotpManagementCard bind:totpEnabled />
	{/if}
</div>
