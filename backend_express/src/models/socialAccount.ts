export interface SocialAccount {
  id: string;
  user_id: string;
  platform: 'youtube' | 'instagram' | 'tiktok';
  platform_account_id: string;
  platform_username: string;
  access_token: string;
  refresh_token: string;
  token_expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export const SOCIAL_PLATFORMS = ['youtube', 'instagram', 'tiktok'] as const;
