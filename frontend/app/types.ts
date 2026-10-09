export interface DatabaseDetails {
    port?: number;
    username?: string;
    type?: string;
    database_id?: string;
}

export interface DatabaseStatus {
    status: boolean | null;
    error?: string;
    details: DatabaseDetails;
}

export interface ServerDatabaseStatus {
    ping: boolean;
    ping_error?: string;
    databases: {
        [dbName: string]: DatabaseStatus;
    };
}

export interface ApplicationStatus {
    ping: boolean;
    ping_error?: string;
    urls: {
        [url: string]: {
            status: boolean;
            error?: string;
        };
    };
    details: {
        urls: string[];
    };
}

export interface EnvironmentDatabaseGroup {
    [serverName: string]: ServerDatabaseStatus;
}

export interface EnvironmentApplicationGroup {
    [serverName: string]: ApplicationStatus;
}

export interface StatusResponse {
    database?: {
        [env: string]: EnvironmentDatabaseGroup;
    };
    application?: {
        [env: string]: EnvironmentApplicationGroup;
    };
}
