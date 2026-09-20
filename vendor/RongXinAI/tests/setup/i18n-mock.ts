// Vitest 共享 mock：i18n 服务
// 项目实际使用的是 i18nService（无 useTranslation hook）
// 这个 mock 让测试能正常运行

export const i18nMock = {
  t: (key: string) => key,
  subscribe: () => () => undefined,
  getLanguage: () => 'zh',
};
