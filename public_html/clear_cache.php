<?php
if (function_exists('opcache_reset')) {
    opcache_reset();
    echo 'opcache reset OK';
} else {
    echo 'opcache not available';
}
 = '/home/gomoncli/public_html/sitepro/a19c9ec17aa700fbe3c8ab3f51a1f461.php';
if (function_exists('opcache_invalidate')) {
    opcache_invalidate(, true);
    echo ' | file invalidated';
}
