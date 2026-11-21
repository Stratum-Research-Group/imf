#pragma once
#include <string>
#include <unordered_map>
#include <vector>
#include <fstream>
#include <sstream>
#include <iostream>

namespace imf {

class SimpleTokenizer {
public:
    std::unordered_map<int64_t, std::string> id_to_token;
    std::unordered_map<std::string, int64_t> token_to_id;

    bool load(const std::string& path) {
        std::ifstream f(path);
        if (!f.is_open()) return false;
        std::string line;
        // Parse simple JSON or key-value map if available, or build basic byte fallback
        while (std::getline(f, line)) {
            // Basic line scanner for "token": id
            auto colon = line.find(':');
            if (colon != std::string::npos) {
                auto q1 = line.find('"');
                auto q2 = line.find('"', q1 + 1);
                if (q1 != std::string::npos && q2 != std::string::npos && q2 < colon) {
                    std::string token = line.substr(q1 + 1, q2 - q1 - 1);
                    std::string id_str = line.substr(colon + 1);
                    // trim
                    while (!id_str.empty() && (id_str.back() == ',' || id_str.back() == ' ' || id_str.back() == '\r')) id_str.pop_back();
                    try {
                        int64_t id = std::stoll(id_str);
                        token_to_id[token] = id;
                        id_to_token[id] = token;
                    } catch (...) {}
                }
            }
        }
        return !id_to_token.empty();
    }

    std::string decode(int64_t id) const {
        auto it = id_to_token.find(id);
        if (it != id_to_token.end()) {
            std::string s = it->second;
            // unescape basic spaces if represented as Ġ or 
            if (s.rfind("Ġ", 0) == 0) s = " " + s.substr(2);
            if (s.rfind(" ", 0) == 0) s = " " + s.substr(3);
            return s;
        }
        return " ";
    }
};

} // namespace imf
