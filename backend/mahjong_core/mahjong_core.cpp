#include <vector>
#include <algorithm>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

// Simplified win check: 4 melds + 1 pair
bool is_win(const std::vector<int>& tiles) {
    if (tiles.size() != 14) return false;
    int counts[40] = {0};
    for (int t : tiles) {
        if (t < 1 || t > 39) return false;
        counts[t]++;
    }
    for (int i = 1; i <= 39; ++i) {
        if (counts[i] >= 2) {
            counts[i] -= 2;
            int melds = 0;
            int temp[40];
            std::copy(counts, counts+40, temp);
            for (int j = 1; j <= 39; ++j) {
                while (temp[j] >= 3) { temp[j] -= 3; melds++; }
                while (j <= 27 && temp[j] && temp[j+1] && temp[j+2]) {
                    temp[j]--; temp[j+1]--; temp[j+2]--; melds++;
                }
            }
            if (melds == 4) return true;
            counts[i] += 2;
        }
    }
    return false;
}

PYBIND11_MODULE(mahjong_core, m) {
    m.def("is_win", &is_win, "Simplified win check, input 14 tiles, return true if win");
}
