#include "httplib.h"


int main() {
    httplib::Server svr;
    svr.Get("/health", [](const httplib::Request&, httplib::Response& res) {
        res.status = 200;
        res.set_content("OK", "text/plain");
    });

    svr.listen("0.0.0.0", 8080);
}
