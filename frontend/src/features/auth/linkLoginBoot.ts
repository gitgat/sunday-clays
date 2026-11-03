// Imported first by main.tsx: ES modules evaluate in import order, so this strips `p` before the
// App module creates the router (or anything else reads the URL).
import { captureLinkPassword } from './linkLogin';

captureLinkPassword();
