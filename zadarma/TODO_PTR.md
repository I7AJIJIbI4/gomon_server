# Pull-to-Refresh — Відомі проблеми

## Статус: НЕ ПРАЦЮЄ на Android TWA

### Проблема
Pull-to-refresh не спрацьовує в Android TWA (Trusted Web Activity) додатку.
JS touchstart/touchmove/touchend listeners на document працюють в Safari і Chrome browser,
але в TWA touch events перехоплюються нативним Chrome engine до нашого JS.

### Що було зроблено
- `overscroll-behavior-y: none` на html,body — блокує Chrome native PTR
- `overscroll-behavior: contain` на .screen і .screen-scroll
- Touch listeners на document level
- activeScreen() правильно визначає адмін-екрани (position:fixed)
- doRefresh() підтримує всі екрани (client + admin)

### Можливі рішення (не реалізовані)
1. **Кнопка "Оновити"** на кожному екрані замість жесту
2. **Auto-refresh** по таймеру (кожні 30-60с) для ключових екранів
3. **Перехід на WebView** замість TWA — дає більше контролю над touch events
4. **Android native pull-to-refresh** через SwipeRefreshLayout в TWA wrapper

### Workaround для користувачів
- Переключення між вкладками оновлює дані автоматично
- Адмін-месенджер має auto-poll кожні 10 секунд
- Календар і статистика завантажуються при кожному заході на вкладку
