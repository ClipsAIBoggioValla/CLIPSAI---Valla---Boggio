# Spark Admin — Referencia de Diseño

> Extraído de `spark-admin-1.0.0/` (template Bootstrap 5). **No es código del proyecto**: resumen para que `frontend_react` y `frontend_vue` compartan tokens. No se modificó ningún componente.

Archivos leídos:
- `spark-admin-1.0.0/assets/css/main.css` (~3187 líneas, 24 secciones)
- `spark-admin-1.0.0/index.html`, `tables-basic.html`, `ui-buttons.html`, `ui-forms.html`, `page-login.html`, `page-404.html`

---

## 1. Paleta de Colores (variables `:root`)

Fuente literal en `main.css` §2 (líneas 53–96):

```css
:root {
  --bs-body-bg: #F4F6F5;               /* canvas */
  --brand-forest-dark: #051C12;        /* sidebar / brand */
  --brand-forest-medium: #072F1F;      /* alert banner / dark card / primary btn */
  --brand-forest-light: #1A3E30;       /* hover en fondo oscuro */
  --brand-lime: #B4F105;               /* acento lima-verde */
  --brand-lime-hover: #c1f824;
  --brand-lime-translucent: rgba(180, 241, 5, 0.15);

  --text-main: #0B130F;                /* encabezados, labels */
  --text-muted-green: #6C7E75;         /* secundario */
  --text-sidebar-muted: #879A91;       /* links inactivos sidebar */

  --card-background: #FFFFFF;
  --border-light: #E9EFEF;
  --border-dark-green: rgba(255,255,255,0.1);

  --sys-green: #22C55E;  --sys-green-bg: #DCFCE7;
  --sys-red: #EF4444;    --sys-red-bg: #FEE2E2;
  --sys-orange: #F97316; --sys-orange-bg: #FFEDD5;
}
```

### Reglas de uso
- **Sidebar**: `background: var(--brand-forest-dark)`, `border-right: 1px solid var(--border-dark-green)`, ancho `280px` (minimizado `80px`). Links inactivos `var(--text-sidebar-muted)`, activos `color:#FFF` + `background: rgba(255,255,255,0.05)` + indicador lateral `width:4px` `background: var(--brand-lime)` (`.sidebar-menu-link.active::before`). Badge `background: var(--brand-lime)` `color: var(--brand-forest-dark)`.
- **Acento lima**: CTA primario secundario (`btn-custom-secondary`, `progress-bar bg-lime-accent`), hover `var(--brand-lime-hover)`, focus ring `0 0 0 3px var(--brand-lime-translucent)`, highlight en tabla `background: rgba(180,241,5,0.03)` (`.table-custom tbody tr:hover`).
- **Texto**: `var(--text-main)` sobre canvas/ cards; `var(--text-muted-green)` para subtítulos, placeholders; `#FFFFFF` dentro de `alert-green-card` / `promo-banner-card` / sidebar.
- **Estados de alerta / sistema**:
  - `.alert-custom-success` → `bg:#f0fdf4` `border:#bbf7d0` `text:#166534`
  - `.alert-custom-danger` → `bg:#fef2f2` `border:#fecaca` `text:#991b1b`
  - `.alert-custom-warning` → `bg:#fffbeb` `border:#fef3c7` `text:#92400e`
  - `.alert-custom-info` → `bg:#f0f9ff` `border:#bae6fd` `text:#075985`
  - `.alert-custom-primary` → `rgba(7,47,31,0.04)` / `rgba(7,47,31,0.08)` / `var(--brand-forest-dark)`
  - Tabla badges: `.badge-table.success` `rgba(34,197,94,0.1)` / `var(--sys-green)`; `.pending` naranja; `.failed` rojo (con dot animado).
- **Canvas**: `body { background: var(--bs-body-bg) }`, contraste cálido: tarjetas blancas + sombras suaves.

---

## 2. Tipografía y Espaciados

### Tipografía
- **Fuente única**: `@import Plus Jakarta Sans (300;400;500;600;700;800)` (`--bs-body-font-family`). Aplicada en `body`, `flatpickr`, y `dropdown-menu-custom`.
- **Body**: `font-size: 0.925rem`, `font-weight: 500`, `letter-spacing: -0.01em`, `-webkit-font-smoothing: antialiased`.
- **Encabezados** `h1–h6`: `font-weight: 700`, `letter-spacing: -0.025em`, `color: var(--text-main)`.
  - `.page-title`: `1.75rem` (`index.html`), `.login-title` `1.5rem 800`, `.error-title-huge` `7.5rem 800` con `gap:0.15em`, `.promo-title` `1.5rem 800`, `.card-title` `1.1rem 700`, `.stat-value` `2rem 800 -0.03em`.
- **Sidebar**: `brand 1.35rem 700`, `menu-title 0.7rem 700 uppercase letter-spacing:0.12em opacity:0.6`, `menu-link 0.95rem 500` (activo 600), `submenu 0.875rem`.
- **Labels**: `.stat-label 0.875rem 500 muted`, `.form-label-custom 0.85rem 700`, `.login-form-label 0.8rem 700`.
- **Links**: `color: var(--brand-forest-medium)`, hover `var(--brand-lime-hover)` con `transition: all 0.25s ease-in-out`.

### Espaciados y Layout
- **Layout**: `--sidebar-width: 280px`, `--navbar-height: 80px`. `.main-wrapper { margin-left: var(--sidebar-width); padding: 2rem 2.5rem; min-height:100vh }`. Responsive `@max-width:1200px` → sidebar `transform: translateX(-100%)`, main `margin-left:0; padding:1.5rem`.
- **Navbar** `.navbar-custom` sticky `backdrop-filter: blur(12px)` `background: rgba(244,246,245,0.85)`, compensa main-wrapper (`margin: -2rem -2.5rem`), `padding:1.25rem 2.5rem`, grid `1fr 480px 1fr`, border `rgba(0,0,0,0.05)`.
- **Page header**: `.page-header { display:flex; justify-content:space-between; margin-bottom:2rem; gap:1.5rem }` (columna en `768px`).
- **Cards**: `padding:1.75rem`, `margin-bottom:1.5rem`, `gap:1.5rem` en grids (`row g-4` ~1.5rem). `.table-card-custom` `margin-bottom:1.25rem`, `.table-custom th/td padding:1rem 1.25rem`, `.custom-list gap:0.85rem`, `.transaction-list gap:0.75rem`.
- **Radios / Shadows**:
  ```css
  --radius-xxl: 24px; --radius-xl: 18px; --radius-lg: 14px; --radius-md: 10px; --radius-sm: 6px;
  --shadow-sm: 0 2px 8px rgba(11,19,15,0.02);
  --shadow-md: 0 10px 30px rgba(11,19,15,0.04);
  --shadow-lg: 0 20px 50px rgba(11,19,15,0.08);
  ```
  Uso: card `var(--radius-xxl)` `var(--shadow-md)`, `table-card-custom` `var(--radius-xl)`, `btn-custom` `var(--radius-lg)`, `form-control` `var(--radius-lg)`, login inputs `var(--radius-lg)`.

---

## 3. Patrones de Componentes (según `main.css`)

> Cero estilos inline: toda variante reutiliza clases `var(--*)`. Animaciones comunes: `transition: all 0.25s ease-in-out`, `transform: scale(0.97)` en `:active`, `@keyframes dropdownFadeIn`, `statusPulse`, `redPulse`, `asteriskSpin`.

### Cards
- **Base** `.card` (líneas 855–864): `background: var(--card-background)`, `border:none`, `border-radius: var(--radius-xxl)`, `padding:1.75rem`, `box-shadow: var(--shadow-md)`, `overflow:hidden`. Header `.card-header` flex space-between sin borde; título `.card-title 1.1rem 700`.
- **Stat** `.card-stat { height:100% }`: label `0.875rem muted`, valor `2rem 800`, tendencia `.trend-badge` `0.785rem 600` (`trend-up: var(--sys-green)` / `trend-down: var(--sys-red)`), sparkline con `margin: -1.75rem` para ocupar footer.
- **Alerta oscura** `.alert-green-card` (`--brand-forest-medium`) `min-height:165px` con forma SVG `alert-green-bg-shape` `120px` rotada `15deg` → `45deg` en hover, badge `rgba(255,255,255,0.1)` + dot pulsante rojo `redPulse`.
- **Tabla** `.table-card-custom` `bg:#FFF` `radius: var(--radius-xl)` `border: rgba(11,19,15,0.06)` `shadow-sm`; header `.table-header-control padding:1.25rem border-bottom rgba(11,19,15,0.06)` + búsqueda `table-search-input`, footer `.table-footer-control` con paginación activa `bg: var(--brand-forest-medium)`.
- **Promo / Right panel** `.promo-banner-card` `#E2E8DF` `radius: var(--radius-xxl)` `min-height:250px` + SVG lima `promo-banner-bg-shape`; `right-panel-wrapper` + donas con `chart-legends-container` `var(--bs-body-bg)` `radius: var(--radius-lg)`.
- **Lista** `.custom-list` / `.transaction-list`: filas `padding:0.85rem 1rem` `bg: #FFF` `radius: var(--radius-xl)` hover `var(--bs-body-bg)` / `rgba(5,28,18,0.06)`, icono `44px` `bg: var(--bs-body-bg)` `radius:50rem`.
- **Login / 404** `.login-card` (`.error-card-custom` hereda) `max-width:450px` `radius: var(--radius-xxl)` `padding:2.5rem` `shadow: var(--shadow-lg)` hover `translateY(-2px)`, fondo shapes `radial-gradient(var(--brand-lime-translucent))` 300/400px.

### Botones
- **Base** `.btn-custom`: `inline-flex gap:0.5rem 0.875rem 600 padding:0.6rem 1.25rem radius: var(--radius-lg) transition: cubic-bezier(0.4,0,0.2,1)`. Size `sm 0.35rem 0.75rem 0.75rem` / `lg 0.75rem 1.75rem 1rem`.
  - `primary`: `bg/border: var(--brand-forest-medium)` `#FFF` → hover `var(--brand-forest-dark)`.
  - `secondary`: `bg/border: var(--brand-lime)` `#072F1F` → hover `var(--brand-lime-hover)`.
  - `light`: `#F8FAF9` / `rgba(11,19,15,0.08)` → hover `#EEF2F0`.
  - `danger`/`warning`: rojo/ámbar sólidos; outlines `outline-primary/secondary/danger` con hover fill.
- **Especializados**: `.btn-quick-action` `var(--brand-forest-medium)` `radius: var(--radius-lg)` `padding:0.5rem 1.15rem 0.825rem 700` con hover glow `var(--brand-lime-translucent)`; `.btn-dark-custom` `var(--text-main)` pill `50rem`; `.btn-login` igual que primary pero `padding:0.85rem` full-width con arrow `translateX(3px)`; `.btn-promo` `var(--brand-forest-dark)` pill full-width; `.btn-table-action` `32px` `bg:#FFF` `border: rgba(11,19,15,0.1)` hover `var(--brand-forest-medium)` `#FFF` (delete → `var(--sys-red)`); `.navbar-action-btn` `42px` `radius: var(--radius-lg)` `bg:#FFF` `border: var(--border-light)` + badge `11px` `var(--sys-green)` pulsante.

### Inputs / Forms
- **`.form-control-custom`** (`1rem 0.875rem 500`): `bg:#FFF` `border: rgba(11,19,15,0.12)` `radius: var(--radius-lg)` `padding:0.6rem 1rem`; focus `border: var(--brand-forest-medium)` `box-shadow: 0 0 0 3px rgba(7,47,31,0.08)`; placeholder `var(--text-muted-green) 0.5`; disabled `bg:#F8FAF9` `0.8`. Variantes `sm/lg`.
- **`.form-select-custom`** idem + `background-image` svg chevron `stroke #072F1F`.
- **Search pills**: `.navbar-search-input` `100%` `bg:#FFF` `border: var(--border-light)` `radius: 50rem` `padding:0.65rem 1.25rem pr:2.75rem` `shadow-sm`; focus `rgba(5,28,18,0.25)`.
- **Login input** `.login-input`: `bg: var(--bs-body-bg)` `border: var(--border-light)` `radius: var(--radius-lg)` `padding:0.8rem 1.25rem 0.8rem 2.85rem` `600` + icono absoluto `1.25rem`; focus `bg:#FFF` `border: var(--brand-forest-medium)` `shadow: 0 0 0 4px var(--brand-lime-translucent)`.
- **Checks / Radios / Switches** `.form-check-input-custom` `18px` `border: rgba(11,19,15,0.15)` focus `var(--brand-lime-translucent)` checked `bg: var(--brand-lime)` `border: var(--brand-lime)` con SVG check lime; switch `.form-switch-input-custom` `38×20px` pill `50rem` knob `16px` `translateX(18px)` checked `bg: var(--brand-forest-medium)`.
- **Input group** `.input-group-custom` `radius: var(--radius-lg)` `border: rgba(11,19,15,0.12)` + `focus-within` igual que control; `input-group-text-custom` `#F8FAF9`.
- **Validación**: `.is-invalid-custom` `border: var(--sys-red)` `shadow rgba(239,68,68,0.08)` ; `.is-valid-custom` verde; feedback `0.75rem 700` rojo/verde.
- **Date picker** `flatpickr-custom` no aplica a CLIPSAI (solo referencia): `324px` `radius:20px` `shadow-lg`, selected `bg: var(--brand-forest-medium)` `#FFF`.

### Otros patrones
- **Dropdowns** `.dropdown-menu-custom / -quick-action / -profile / -notification` siempre `bg:#FFF` `border: var(--border-light)` `radius: var(--radius-xl/lg)` `shadow: var(--shadow-lg)` `animation: dropdownFadeIn 0.2s`, item `0.85rem 600` hover `var(--bs-body-bg)` `var(--text-main)`; danger hover `var(--sys-red-bg)`.
- **Footer** `.footer-custom` `margin-top:auto` `padding-top:1.25rem` `border-top: rgba(11,19,15,0.06)` `0.85rem muted`, logo `var(--text-main) 700` + asterisk animado `rotateLogo 12s`, heart `heartBeat 1.5s`.
- **Progress** `.progress height:10px bg: var(--bs-body-bg) radius:50rem` + `.progress-bar` `bg-forest-medium / bg-lime-accent / bg-brand-orange`.
- **Zero inline style**: helpers `.z-index-2`, `.sparkline-card-footer { margin: -1.75rem }`, `.w-38/45/50/65/75/85`.

> Guía para CLIPSAI: replicar tokens en `src/tokens.css` o Tailwind config compartido; no importar Bootstrap ni `main.css` directo. Cards futuras deben usar `radius-xxl + shadow-md + border-light`; botones primarios `brand-forest-medium`, secundarios `brand-lime`; inputs siempre con focus ring `brand-lime-translucent`.

