package com.europrice.app;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.view.View;

public class MainActivity extends Activity {
    private static final String APP_URL = "https://raw.githubusercontent.com/oleksiy78/EuroPrice/main/index.html";
    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WebView web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        web.setWebViewClient(new WebViewClient());
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        web.loadUrl(APP_URL);
        setContentView(web);
    }
    @Override public void onBackPressed() {
        WebView web = (WebView) findViewById(android.R.id.content).findViewById(0);
        super.onBackPressed();
    }
}
