import { createContext, useContext, useState, ReactNode } from "react";

interface UserContextType {
  username:      string;
  token:         string | null;
  studentId:     string | null;
  isAuthenticated: boolean;
  /** Lightweight username-only login (used as offline fallback). */
  setUsername:   (name: string) => void;
  /** Full login — sets username, bearer token, and studentId atomically. */
  setLoginData:  (username: string, token: string, studentId: string) => void;
  logout:        () => void;
}

const UserContext = createContext<UserContextType>({
  username:        "",
  token:           null,
  studentId:       null,
  isAuthenticated: false,
  setUsername:     () => {},
  setLoginData:    () => {},
  logout:          () => {},
});

export const UserProvider = ({ children }: { children: ReactNode }) => {
  const [username, setUsernameState] = useState<string>(() =>
    localStorage.getItem("academiq_username") ?? "",
  );
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("academiq_token"),
  );
  const [studentId, setStudentId] = useState<string | null>(() =>
    localStorage.getItem("academiq_student_id"),
  );

  const isAuthenticated = username.length > 0;

  const setUsername = (name: string) => {
    setUsernameState(name);
    localStorage.setItem("academiq_username", name);
  };

  const setLoginData = (uname: string, tkn: string, sid: string) => {
    setUsernameState(uname);
    setToken(tkn);
    setStudentId(sid);
    localStorage.setItem("academiq_username",   uname);
    localStorage.setItem("academiq_token",      tkn);
    localStorage.setItem("academiq_student_id", sid);
  };

  const logout = () => {
    setUsernameState("");
    setToken(null);
    setStudentId(null);
    localStorage.removeItem("academiq_username");
    localStorage.removeItem("academiq_token");
    localStorage.removeItem("academiq_student_id");
  };

  return (
    <UserContext.Provider
      value={{ username, token, studentId, isAuthenticated, setUsername, setLoginData, logout }}
    >
      {children}
    </UserContext.Provider>
  );
};

export const useUser = () => useContext(UserContext);
