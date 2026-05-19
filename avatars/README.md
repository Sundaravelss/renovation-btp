# Avatars

Per-role avatar assets used by `<AvatarMedia>` (`components/shared/avatar-media.tsx`).

## Layout

```
public/avatars/
├── stylized/      # primary style (used on /agents)
│   └── <role>.{mp4, png, poster.jpg}
└── photoreal/     # comparison style (used on /agents-realistic)
    └── <role>.{mp4, png, poster.jpg}
```

## Roles shipped

`assistant`, `commercial`, `comptable`, `customer-care`, `marketing`,
`recrutement`, `sales`, `social-media`.

## Per-role artefacts

| Style     | Role          | mp4 | png | poster.jpg |
|-----------|---------------|-----|-----|------------|
| stylized  | assistant     | yes | yes | yes |
| stylized  | commercial    | yes | yes | yes |
| stylized  | comptable     | yes | yes | yes |
| stylized  | customer-care | yes | yes | yes |
| stylized  | marketing     | yes | yes | yes |
| stylized  | recrutement   | yes | yes | yes |
| stylized  | sales         | no  | yes | yes |
| stylized  | social-media  | no  | yes | yes |
| photoreal | assistant     | yes | yes | yes |
| photoreal | commercial    | yes | yes | yes |
| photoreal | comptable     | yes | yes | yes |
| photoreal | customer-care | yes | yes | yes |
| photoreal | marketing     | yes | yes | yes |
| photoreal | recrutement   | yes | yes | yes |
| photoreal | sales         | yes | yes | yes |
| photoreal | social-media  | no  | yes | yes |

When the `.mp4` is missing, `<AvatarMedia>` falls back to the static `.png`
gracefully via the `<video>` element's error handling and the slow-network
gate in `useShouldUseStillImage`.

## Production notes

- `.png` ships as the still / poster fallback (also used on slow networks,
  reduced-motion, Save-Data, and SSR).
- `.poster.jpg` is the cinematic poster frame used by the `<video>` element
  before the loop starts streaming.
- `.mp4` is the looping clip; muted, autoplay, loop, playsInline.

Future iteration (out of scope for this batch): produce `.alpha.webm` +
`.alpha.png` matted variants and a 256px `.alpha.thumb.webp` for cards.

## Hard rules

- Do **not** rename these files. The `<AvatarMedia>` component pins to the
  `<role>` slug. Multiple personas may share one avatar via the
  `avatarSlug` field in the data layer.
- Do **not** edit the assets in place — they are the canonical export from
  the i2v / matting pipeline.
