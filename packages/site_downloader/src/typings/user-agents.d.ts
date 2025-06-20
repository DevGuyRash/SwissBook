declare module 'user-agents' {
    /** Subset of the real API – enough for our code. */
    export default class UserAgent {
      toString(): string;
    }
  }
  