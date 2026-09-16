// .dependency-cruiser.cjs
module.exports = {
  forbidden: [
    { name: 'core-no-ui',       from: { path: '^packages/core' },   to: { path: '^packages/(ui|adapters|plugins)' } },
    { name: 'kernel-no-core',   from: { path: '^packages/kernel' }, to: { path: '^packages/core' } },
    { name: 'ui-no-adapters',   from: { path: '^packages/ui' },      to: { path: '^packages/adapters' } },
    { name: 'plugins-only-api', from: { path: '^packages/plugins' }, to: { path: '^packages/core/(?!ports)' } },
    { name: 'no-circular',       from: {}, to: { circular: true } },
  ],
};
