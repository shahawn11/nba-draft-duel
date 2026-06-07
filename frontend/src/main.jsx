import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './styles.css'

// NOTE: no React.StrictMode — its dev double-mount opens/closes the live PvP
// WebSocket twice, which breaks matchmaking (a player can self-match) and logs
// "WebSocket closed before connection established".
createRoot(document.getElementById('root')).render(<App />)
