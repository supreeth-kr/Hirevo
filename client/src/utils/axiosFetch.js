import axios from "axios";

const axiosFetch = axios.create({
    // Keep local development working even when no .env file has been created.
    baseURL: import.meta.env.VITE_API_URL || "http://localhost:8080/api",
    withCredentials: true
});

export default axiosFetch;
