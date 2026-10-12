const hosted = location.hostname.endsWith('.robotarn.org');
export const crewUrl = (id?: string) => `${hosted ? 'https://crew-aigcs-skyhack.robotarn.org' : ''}/crew${id ? '/' + encodeURIComponent(id) : ''}`;
export const commanderUrl = hosted ? 'https://commander-aigcs-skyhack.robotarn.org/commander' : '/commander';
export const crewHost = location.hostname.startsWith('crew-aigcs-skyhack.');
