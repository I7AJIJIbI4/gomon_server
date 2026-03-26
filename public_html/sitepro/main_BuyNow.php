<?php

require_once dirname(__FILE__).'/GatewayPaypal.php';

$id = $pluginData->elemId;
$clientId = isset($pluginData->clientId) ? $pluginData->clientId : null;
$clientSecret = isset($pluginData->clientSecret) ? $pluginData->clientSecret : null;
$demo = (isset($pluginData->demo) && $pluginData->demo);
$isStore = (isset($pluginData->store) && $pluginData->store);
if ($clientId && $clientSecret) {
    ?>
    <script type="text/javascript">
        (function() {
            var baseUrl = $('base').attr('href');
            var getGatewayUrl = function(method) {
                return baseUrl + method + '/Paypal';
            };
            $('#<?php echo $id; ?>_form').on('submit', function() {
                var data = {}, i, len, elem;
                for (i=0, len = this.elements.length; i < len; i++) {
                    elem = this.elements[i];
                    if (!elem.name) continue;
                    data[elem.name] = elem.value;
                }
                data.input = '<?php $auth = new GatewayPaypalV2Auth($clientId, $clientSecret, $demo); echo $auth->parseFromObject(); ?>';
                $.ajax({
                    url: getGatewayUrl('requestCreatePayment'),
                    data: data,
                    type: 'post',
                    dataType: 'json',
                    success: function(resp) {
                        if (!resp.url) {
                            alert((resp.error ? resp.error : 'Error occurred. Please try again later.'));
                        } else {
                            location.href = resp.url;
                        }
                    }
                });
                return false;
            });
        })();
    </script>
<?php
} else {
    $localeIdx = array_search($pluginData->currLangLocale, GatewayPaypalV1::$supportedLocales);
    $useLocale = $localeIdx ? GatewayPaypalV1::$supportedLocales[$localeIdx] : 'en_US';
    ?>
    <input type="hidden" name="item_name" value="<?php echo tr_($pluginData->itemName); ?>" />
    <input type="hidden" name="lc" value="<?php echo $useLocale; ?>" />
    <?php if (!$isStore):
        $baseUrl = getBaseUrl(); ?>
    <input type="hidden" name="return" value="<?php echo $baseUrl.'store-return/Paypal'; ?>" />
    <input type="hidden" name="cancel_return" value="<?php echo $baseUrl.'store-cancel/Paypal'; ?>" />
    <?php endif; ?>
    <?php echo $pluginData->paymentGatewayButton; ?>
<?php } ?>
