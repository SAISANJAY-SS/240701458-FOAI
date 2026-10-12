# ResQAI Citizen App

Flutter Material 3 citizen client. The SOS request is sent to FastAPI when online and stored in `SharedPreferences` when offline. The backend, not the client, calculates priority.

```bash
flutter pub get
flutter run --dart-define=API_BASE_URL=http://localhost:8000
```

On Android emulators use `http://10.0.2.2:8000`; on a physical device use the host machine LAN address.
