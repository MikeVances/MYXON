import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'MYXON',
  description: 'Remote access and monitoring platform for agricultural automation systems',
  lang: 'en-US',

  // GitHub Pages project repo → assets served under /MYXON/
  // Remove this line if using a custom domain or Netlify/Vercel
  base: '/MYXON/',

  head: [
    ['meta', { name: 'theme-color', content: '#1d4ed8' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:title', content: 'MYXON Docs' }],
    ['meta', { property: 'og:description', content: 'Remote access and monitoring for agricultural controllers' }],
  ],

  themeConfig: {
    logo: '/logo.svg',
    siteTitle: 'MYXON Docs',

    nav: [
      { text: 'Guide', link: '/guide/what-is-myxon' },
      { text: 'Dealer', link: '/dealer/overview' },
      { text: 'Customer', link: '/customer/overview' },
      { text: 'OEM / SDK', link: '/oem/overview' },
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Introduction',
          items: [
            { text: 'What is MYXON?', link: '/guide/what-is-myxon' },
            { text: 'Core concepts', link: '/guide/concepts' },
            { text: 'Two deployment scenarios', link: '/guide/scenarios' },
          ],
        },
      ],

      '/dealer/': [
        {
          text: 'Dealer Portal',
          items: [
            { text: 'Overview', link: '/dealer/overview' },
            { text: 'Register devices (Scenario 1)', link: '/dealer/register-devices' },
            { text: 'Activation codes (Scenario 2)', link: '/dealer/activation-codes' },
            { text: 'Invite customers', link: '/dealer/invite-customers' },
            { text: 'Fleet monitoring', link: '/dealer/fleet-monitoring' },
          ],
        },
      ],

      '/customer/': [
        {
          text: 'Customer Portal',
          items: [
            { text: 'Overview', link: '/customer/overview' },
            { text: 'Claim a device (QR code)', link: '/customer/claim-device' },
            { text: 'Device dashboard', link: '/customer/device-dashboard' },
            { text: 'Locations', link: '/customer/locations' },
            { text: 'Alarms', link: '/customer/alarms' },
            { text: 'Access policies', link: '/customer/access-policies' },
          ],
        },
      ],

      '/oem/': [
        {
          text: 'OEM / SDK Integration',
          items: [
            { text: 'Overview', link: '/oem/overview' },
            { text: 'Quick install', link: '/oem/install' },
            { text: 'Agent configuration', link: '/oem/agent-config' },
            { text: 'Activation code flow', link: '/oem/activation-flow' },
            { text: 'LAN auto-discovery', link: '/oem/lan-discovery' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/MikeVances/MYXON' },
    ],

    footer: {
      message: 'MYXON Platform',
      copyright: 'Built for agricultural automation professionals',
    },

    search: {
      provider: 'local',
    },
  },

  markdown: {
    // Mermaid diagrams are rendered natively
    config: (md) => {
      // additional markdown-it plugins can be added here
    },
  },
})
