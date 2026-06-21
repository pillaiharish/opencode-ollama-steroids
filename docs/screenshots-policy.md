# Screenshots Policy

Screenshots can help with browser tests and UI review, but they are also a common leak source.

## Allowed Locally

- localhost UI with fake or public data;
- cropped visual diffs;
- failure screenshots with private browser and terminal details hidden.

## Do Not Publish

- auth screens;
- production dashboards;
- private customer data;
- terminal screenshots with local paths or environment values;
- browser tabs with private titles;
- API responses containing personal or customer data;
- screenshots of raw prompt or session history.

## Storage

Store local screenshots under:

```text
screenshots/
```

The folder is ignored. Public docs should use diagrams, fake examples, or heavily redacted visual evidence.

## Review Requirement

The reviewer should block signoff when UI work claims browser coverage without evidence, or when screenshots contain private data.
