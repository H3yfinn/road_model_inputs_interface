/**
 * api.js
 * Core HTTP client module handling optional communication with the Multinode Energy Modeler FastAPI backend.
 * Engineered using native Fetch API to eliminate external dependency overhead.
 */

// Use relative URLs when served from a real server; fall back to localhost
// only when the file is opened directly (file:// protocol, local dev without server).
const _API_ORIGIN = location.protocol === 'file:' ? 'http://localhost:8000' : '';
const API_BASE_URL = `${_API_ORIGIN}/api/v1/energy-model`;

class EnergyModelAPI {
    
    /**
     * Generic low-level POST request wrapper with integrated server exception parsing.
     * @param {string} endpoint - The target URL path appended to the API base URL.
     * @param {Object} payload - The JSON-serializable body request object.
     * @returns {Promise<Object>} Resolves with the parsed backend response payload.
     */
    static async _post(endpoint, payload, baseUrl = API_BASE_URL) {
        try {
            const response = await fetch(`${baseUrl}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (!response.ok) {
                const errorMessage = typeof data.detail === 'string' 
                    ? data.detail 
                    : JSON.stringify(data.detail) || data.error || 'Unknown server error';
                throw new Error(errorMessage);
            }

            return data;
        } catch (error) {
            console.error(`API POST Network or Server Exception on ${endpoint}:`, error);
            throw error;
        }
    }

    /**
     * Generic low-level GET request wrapper with dynamic query parameter compilation.
     * @param {string} endpoint - The target URL path appended to the API base URL.
     * @param {Object} [params={}] - Key-value mapping representing GET query parameters.
     * @returns {Promise<Object>} Resolves with the parsed backend response payload.
     */
    static async _get(endpoint, params = {}, baseUrl = API_BASE_URL) {
        try {
            const queryString = new URLSearchParams(params).toString();
            const url = queryString ? `${baseUrl}${endpoint}?${queryString}` : `${baseUrl}${endpoint}`;
            
            const response = await fetch(url, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            });

            const data = await response.json();

            if (!response.ok) {
                const errorMessage = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
                throw new Error(errorMessage);
            }

            return data;
        } catch (error) {
            console.error(`API GET Network or Server Exception on ${endpoint}:`, error);
            throw error;
        }
    }

    // ==========================================
    // PUBLIC IMPLEMENTATION METHODS
    // ==========================================

    /**
     * Fetches the top-down macroeconomic target sum to seed the root layer of the tree.
     */
    static async initialize(economy, year, sectorFlow) {
        return await this._post('/initialize', {
            economy: economy,
            year: year,
            sector_flow: sectorFlow
        });
    }

    /**
     * Retrieves the dynamic collection of non-zero active fuels from the APEC macro balance sheets.
     */
    static async getActiveFuels(economy, year, sectorFlow) {
        return await this._get('/metadata/active_fuels', {
            economy: economy,
            year: year,
            sector_flow: sectorFlow
        });
    }

    /**
     * Transmits the recursive tree state data structure for mass balance verification.
     * Naturally forwards min_weight and max_weight attributes present in the node references.
     */
    static async validateTree(payload) {
        return await this._post('/validate_tree', payload);
    }

    /**
     * Executes the mathematical optimization pipeline on the backend to balance fuel items.
     * Passes the recursive tree state containing optional boundary constraints.
     */
    static async optimizeTree(payload) {
        return await this._post('/optimize_tree', payload);
    }

    /**
     * Triggers workbook rendering for final LEAP alignment export.
     */
    static async exportToLeap(payload) {
        return await this._post('/export', payload);
    }
}
