import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// Mock SvelteKit's $app/env modules for the test environment: every variable unset.
vi.mock('$app/env/public', () => ({
	PUBLIC_API_URL: undefined
}));
vi.mock('$app/env/private', () => ({
	INTERNAL_API_URL: undefined,
	DEV_SKIP_AUTH: undefined,
	BOOTSTRAP_TOKEN_FILE: undefined
}));
