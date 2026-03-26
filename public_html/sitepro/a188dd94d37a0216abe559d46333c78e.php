<!DOCTYPE html>
<html lang="uk">
<head>
	<script type="text/javascript">
			</script>
	<meta http-equiv="content-type" content="text/html; charset=utf-8" />
	<title><?php echo htmlspecialchars((isset($seoTitle) && $seoTitle !== "") ? $seoTitle : "Contacts"); ?></title>
	<base href="{{base_url}}" />
	<?php echo isset($sitemapUrls) ? (generateCanonicalUrl($sitemapUrls)."\n") : ""; ?>	
	
						<meta name="viewport" content="width=device-width, initial-scale=1" />
					<meta name="description" content="<?php echo htmlspecialchars((isset($seoDescription) && $seoDescription !== "") ? $seoDescription : "Контакти Dr. Gomon Cosmetology"); ?>" />
			<meta name="keywords" content="<?php echo htmlspecialchars((isset($seoKeywords) && $seoKeywords !== "") ? $seoKeywords : "косметолог,Черкаси,косметологічний кабінет,студія косметології,пілінг,маска,відбілювання зубів,аугментація,гіалуронова кислота,гіалуронідаза,гіпергідроз,бруксизм,догляд за шкірою обличчя,мезотерапія,ботулінотерапія,біоревіталізація,апаратна косметологія,ін,єкційна косметологія,ультразвукова чистка,скрабер,скраб,корекція обличчя,аугментація скул,аугментація губ,аугментація підборіддня,корекція підборіддя,корекція губ,заповнення носогубних складок,розгладження зморшок,облисіння,ріст волосся,лікування акне,Контакти"); ?>" />
			
	<!-- Facebook Open Graph -->
		<meta property="og:title" content="<?php echo htmlspecialchars((isset($seoTitle) && $seoTitle !== "") ? $seoTitle : "Contacts"); ?>" />
			<meta property="og:description" content="<?php echo htmlspecialchars((isset($seoDescription) && $seoDescription !== "") ? $seoDescription : "Контакти Dr. Gomon Cosmetology"); ?>" />
			<meta property="og:image" content="<?php echo htmlspecialchars((isset($seoImage) && $seoImage !== "") ? "{{base_url}}".$seoImage : "{{base_url}}gallery_gen/9558c7621adb906341ebf2349ec43222_fit.jpg"); ?>" />
			<meta property="og:type" content="article" />
			<meta property="og:url" content="{{curr_url}}" />
		<!-- Facebook Open Graph end -->

		<meta name="generator" content="Конструктор сайтов" />
			<script src="js/common-bundle.js?ts=20260307122649" type="text/javascript"></script>
	<script src="js/a188dd94d37a0216abe559d46333c78e-bundle.js?ts=20260307122649" type="text/javascript"></script>
	<link href="css/common-bundle.css?ts=20260307122649" rel="stylesheet" type="text/css" />
	<link href="css/a188dd94d37a0216abe559d46333c78e-bundle.css?ts=20260307122649" rel="stylesheet" type="text/css" id="wb-page-stylesheet" />
	<ga-code/><link rel="apple-touch-icon" type="image/png" sizes="120x120" href="gallery/favicons/favicon-120x120.png"><link rel="icon" type="image/png" sizes="120x120" href="gallery/favicons/favicon-120x120.png"><link rel="apple-touch-icon" type="image/png" sizes="152x152" href="gallery/favicons/favicon-152x152.png"><link rel="icon" type="image/png" sizes="152x152" href="gallery/favicons/favicon-152x152.png"><link rel="apple-touch-icon" type="image/png" sizes="180x180" href="gallery/favicons/favicon-180x180.png"><link rel="icon" type="image/png" sizes="180x180" href="gallery/favicons/favicon-180x180.png"><link rel="icon" type="image/png" sizes="192x192" href="gallery/favicons/favicon-192x192.png"><link rel="apple-touch-icon" type="image/png" sizes="60x60" href="gallery/favicons/favicon-60x60.png"><link rel="icon" type="image/png" sizes="60x60" href="gallery/favicons/favicon-60x60.png"><link rel="apple-touch-icon" type="image/png" sizes="76x76" href="gallery/favicons/favicon-76x76.png"><link rel="icon" type="image/png" sizes="76x76" href="gallery/favicons/favicon-76x76.png"><link rel="icon" type="image/png" href="gallery/favicons/favicon.png">
	<script type="text/javascript">
	window.useTrailingSlashes = false;
	window.disableRightClick = true;
	window.currLang = 'uk';
</script>
	<meta http-equiv="refresh" content="0; url=https://gomonclinic.com/Landing">	
	<!--[if lt IE 9]>
	<script src="js/html5shiv.min.js"></script>
	<![endif]-->

		<script type="text/javascript">
		$(function () {
<?php $wb_form_send_success = popSessionOrGlobalVar("wb_form_send_success"); ?>
<?php if (($wb_form_send_state = popSessionOrGlobalVar("wb_form_send_state"))) { ?>
	<?php if (($wb_form_popup_mode = popSessionOrGlobalVar("wb_form_popup_mode")) && (isset($wbPopupMode) && $wbPopupMode)) { ?>
		if (window !== window.parent && window.parent.postMessage) {
			var data = {
				event: "wb_contact_form_sent",
				data: {
					state: "<?php echo str_replace('"', '\"', $wb_form_send_state); ?>",
					type: "<?php echo $wb_form_send_success ? "success" : "danger"; ?>"
				}
			};
			window.parent.postMessage(data, "<?php echo str_replace('"', '\"', popSessionOrGlobalVar("wb_target_origin")); ?>");
		}
	<?php $wb_form_send_success = false; $wb_form_send_state = null; $wb_form_popup_mode = false; ?>
	<?php } else { ?>
		wb_show_alert("<?php echo str_replace(array('"', "\r", "\n"), array('\"', "", "<br/>"), $wb_form_send_state); ?>", "<?php echo $wb_form_send_success ? "success" : "danger"; ?>");
	<?php } ?>
<?php } ?>
});    </script>
</head>


<body class="site site-lang-uk<?php if (isset($wbPopupMode) && $wbPopupMode) echo ' popup-mode'; ?> " <?php ?>><div id="wb_root" class="root wb-layout-vertical"><div class="wb_sbg"></div><div id="map-container"></div>
    <div id="info-container"></div>

    <script>
        function initMap() {
            // Координаты места
            var myLatLng = {lat: 49.44293634270526, lng: 32.06966843069176};

            // Создаем карту
            var map = new google.maps.Map(document.getElementById('map-container'), {
                center: myLatLng,
                zoom: 15
            });

            // Создаем маркер на карте
            var marker = new google.maps.Marker({
                position: myLatLng,
                map: map,
                title: 'Medical Beauty Bar'
            });

            // Получаем информацию о месте
            var service = new google.maps.places.PlacesService(map);
            service.getDetails({
                placeId: 'ChIJhU5Jx2NL0UARXlBOfDxyI2I' // Замените на place_id вашего места
            }, function(place, status) {
                if (status === google.maps.places.PlacesServiceStatus.OK) {
                    // Выводим информацию о месте
                    document.getElementById('info-container').innerHTML = '<h2>' + place.name + '' +
                        '<p>' + place.formatted_address + '' +
                        '<p>' + place.formatted_phone_number + '' +
                        '<p>' + place.website + '';
                }
            });
        }
    </script><!-- Подключаем Google Maps JavaScript API с вашим ключом --><script src="https://maps.googleapis.com/maps/api/key=GOOGLE_MAPS_KEY_REMOVED&amp;callback=initMap" async defer>
    </script><div id="wb_header_a188dd94d37a0216abe559d46333c78e" class="wb_element wb-sticky wb-layout-element" data-plugin="LayoutElement" data-h-align="center" data-v-align="top"><div class="wb_content wb-layout-horizontal"><div id="a188dd94be463a75dba900fbd0353b25" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18ead322d680080628d287d243cee71" class="wb_element wb-layout-element wb-layout-has-link" data-plugin="LayoutElement"><a class="wb-layout-link" href="{{base_url}}"></a><div class="wb_content wb-layout-horizontal"><div id="a18ead322d6b001e1977180c2349f733" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><h2 class="wb-stl-custom8" style="text-align: center;"><span style="font-size:22px;"><strong><span style="color:#00274b;">Dr. Gomon</span></strong></span></h2>

<h1 class="wb-stl-custom6" style="text-align: center;"><span style="font-size:22px;"><span style="">Cosmetology</span></span></h1>
</div></div></div><div id="a18e8ebeee02009fcb04aeff93212f72" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a188dd94be463e7773075e324b4e59cc" class="wb_element wb-menu wb-prevent-layout-click wb-menu-mobile" data-plugin="Menu"><span class="btn btn-default btn-collapser"><span class="icon-bar"></span><span class="icon-bar"></span><span class="icon-bar"></span></span><?php MenuElement::render((object) array(
	'type' => 'hmenu',
	'dir' => 'ltr',
	'items' => array(
		(object) array(
			'id' => 1,
			'href' => '{{base_url}}',
			'name' => 'Головна',
			'class' => '',
			'children' => array()
		),
		(object) array(
			'id' => 2,
			'href' => 'price',
			'name' => 'Послуги й ціни',
			'class' => '',
			'children' => array(
				(object) array(
					'id' => 5,
					'href' => 'https://gomonclinic.com/price/%D0%90%D0%BF%D0%B0%D1%80%D0%B0%D1%82%D0%BD%D0%B0-%D0%9A%D0%BE%D1%81%D0%BC%D0%B5%D1%82%D0%BE%D0%BB%D0%BE%D0%B3%D1%96%D1%8F',
					'name' => 'Апаратна косметологія',
					'class' => '',
					'children' => array()
				),
				(object) array(
					'id' => 6,
					'href' => 'https://gomonclinic.com/price/%D0%94%D0%BE%D0%B3%D0%BB%D1%8F%D0%B4%D0%BE%D0%B2%D1%96-%D0%9F%D1%80%D0%BE%D1%86%D0%B5%D0%B4%D1%83%D1%80%D0%B8',
					'name' => 'Доглядові процедури',
					'class' => '',
					'children' => array()
				),
				(object) array(
					'id' => 7,
					'href' => 'https://gomonclinic.com/price/%D0%90%D0%BF%D0%B0%D1%80%D0%B0%D1%82%D0%BD%D0%B0-%D0%9A%D0%BE%D1%80%D0%B5%D0%BA%D1%86%D1%96%D1%8F-%D0%A4%D1%96%D0%B3%D1%83%D1%80%D0%B8',
					'name' => 'Апаратна корекція фігури',
					'class' => '',
					'children' => array()
				),
				(object) array(
					'id' => 8,
					'href' => 'https://gomonclinic.com/price/%D0%92%D1%96%D0%B4%D0%B1%D1%96%D0%BB%D1%8E%D0%B2%D0%B0%D0%BD%D0%BD%D1%8F-%D0%97%D1%83%D0%B1%D1%96%D0%B2',
					'name' => 'Косметичне відбілювання зубів',
					'class' => '',
					'children' => array()
				)
			)
		),
		(object) array(
			'id' => 3,
			'href' => 'about_us',
			'name' => 'Про нас',
			'class' => '',
			'children' => array()
		),
		(object) array(
			'id' => 4,
			'href' => 'contacts',
			'name' => 'Контакти',
			'class' => 'wb_this_page_menu_item active',
			'children' => array()
		)
	)
)); ?><div class="clearfix"></div></div></div></div><div id="a188dd94be463f094e15f4bb63aa5685" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a188dd94be46406d239a78d32acc37a2" class="wb_element wb_element_picture wb-anim wb-anim-zoom-in" data-plugin="Picture" title="Instagram"><div class="wb_picture_wrap" style="height: 100%"><div class="wb-picture-wrapper" style="overflow: visible; display: flex"><a href="https://m.instagram.com/dr.gomon" title="Instagram" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="30" viewBox="0 0 1793.982 1793.982" style="direction: ltr; color:#00274b"><text x="129.501415" y="1537.02" font-size="1792" fill="currentColor" style='font-family: "FontAwesome"'></text></svg></a></div></div></div><div id="a188dd94be4641bdb8744d1c11db0d1f" class="wb_element wb_element_picture wb-anim wb-anim-zoom-in" data-plugin="Picture" title="Facebook"><div class="wb_picture_wrap" style="height: 100%"><div class="wb-picture-wrapper" style="overflow: visible; display: flex"><a href="https://m.facebook.com/dr.gomon" title="Facebook" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="30" viewBox="0 0 1793.982 1793.982" style="direction: ltr; color:#00274b"><text x="385.501415" y="1537.02" font-size="1792" fill="currentColor" style='font-family: "FontAwesome"'></text></svg></a></div></div></div><div id="a188dd94be464213c9058d2ac34834c4" class="wb_element wb_element_picture wb-anim wb-anim-zoom-in" data-plugin="Picture" title="Google Maps"><div class="wb_picture_wrap" style="height: 100%"><div class="wb-picture-wrapper" style="overflow: visible; display: flex"><a href="https://goo.gl/maps/pawu2CSnPNZhySMb7" title="Google Maps" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="30" viewBox="0 0 1793.982 1793.982" style="direction: ltr; color:#00274b"><text x="129.501415" y="1537.02" font-size="1792" fill="currentColor" style='font-family: "FontAwesome"'></text></svg></a></div></div></div></div></div></div></div></div></div><div id="wb_main_a188dd94d37a0216abe559d46333c78e" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18eaad72dd8000888df4b05800d8806" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><p class="wb-stl-normal"><span style="color:#00274b;"><span style="background-color:transparent;"><strong><span style="font-size:24px;">Наші контакти</span></strong></span></span></p>
</div><div id="a18ea08ab3de0103e4575789f258ca97" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18f2563b41e00bd149058aa432f2b08" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><p style="text-align: center;"><span class="wb-stl-custom10">Працюємо <strong><em>БЕЗ</em></strong> вихідних, але <strong><em>ТІЛЬКИ</em></strong> за попереднім <a class="docs-creator" data-_="Link" href="javascript:void(0);" data-popup="wb_popup:Messenger?wbPopupMode=1#chat;w=500;h=500;pagePopup=1;" title="запис">записом</a></span></p>
</div><div id="a18ea08ab3de04643680ac2c1299e975" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18ea08ab3de0517b297e1fd6e028794" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18ea08ab3de06657df604849b827cb0" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18ea08ab3de072c908e05a4dbd20d60" class="wb_element wb_element_picture" data-plugin="Picture" title="Maps"><div class="wb_picture_wrap"><div class="wb-picture-wrapper" style="overflow: visible; display: flex"><a href="https://goo.gl/maps/pawu2CSnPNZhySMb7" title="Maps" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 1793.982 1793.982" style="direction: ltr; color:#00274b"><text x="385.501415" y="1537.02" font-size="1792" fill="currentColor" style='font-family: "FontAwesome"'></text></svg></a></div></div></div><div id="a18ea08ab3de081d88870d56beed9bd3" class="wb_element wb_element_picture" data-plugin="Picture" title="phone"><div class="wb_picture_wrap"><div class="wb-picture-wrapper" style="overflow: visible; display: flex"><a href="tel:+380933297777" title="phone"><svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 1793.982 1793.982" style="direction: ltr; color:#00274b"><text x="193.501415" y="1537.02" font-size="1792" fill="currentColor" style='font-family: "FontAwesome"'></text></svg></a></div></div></div><div id="a18ee8901595003eec7693d2e5e47552" class="wb_element wb_element_picture" data-plugin="Picture" title="Direct"><div class="wb_picture_wrap"><div class="wb-picture-wrapper" style="overflow: visible; display: flex"><a href="https://ig.me/m/dr.gomon" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 1793.982 1793.982" style="direction: ltr; color:#00274b"><text x="129.501415" y="1537.02" font-size="1792" fill="currentColor" style='font-family: "FontAwesome"'></text></svg></a></div></div></div><div id="a18ea08ab3de092a6e20e0dc0d80f9bd" class="wb_element wb_element_picture" data-plugin="Picture" title="Email"><div class="wb_picture_wrap"><div class="wb-picture-wrapper" style="overflow: visible; display: flex"><a href="mailto:viktoriia@gomonclinic.com" title="email" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 1793.982 1793.982" style="direction: ltr; color:#00274b"><text x="1.501415" y="1537.02" font-size="1792" fill="currentColor" style='font-family: "FontAwesome"'></text></svg></a></div></div></div></div></div><div id="a18ea08ab3de0adedd4c0d8562c19436" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><p class="wb-stl-custom7">Адреса:<br><span style="color:#00274b;"><a class="docs-creator" data-_="Link" href="https://goo.gl/maps/pawu2CSnPNZhySMb7" target="_blank" title="Maps">вул.Сміляньска, 23, БЦ Галерея, оф. 605, Черкаси</a></span></p>

<p class="wb-stl-custom7"> </p>

<p class="wb-stl-custom7">Тел.:         <strong>                       <a class="docs-creator" data-_="Link" href="viber://chat?number=%2B380996093860" target="_blank" title="Viber">Viber</a>    </strong><a class="docs-creator" data-_="Link" href="https://t.me/+380733103110" target="_blank" title="Telegram">Telegram</a><br><span style="color:#00274b;"><a class="docs-creator" data-_="Link" href="tel:+380733103110"><span><span appcallback_target_phone="+380996093860" id="appCallback_ext-click-03689976930171669">+38(073) 310-31-10</span></span></a></span></p>

<p class="wb-stl-custom7"> </p>

<p class="wb-stl-custom7">Instagram:</p>

<p class="wb-stl-custom7"><a class="docs-creator" data-_="Link" href="https://ig.me/m/dr.gomon" rel="nofollow" target="_blank" title="Direct">Direct @dr.gomon</a></p>

<p class="wb-stl-custom7"><br>
Пошта:<br><a class="docs-creator" data-_="Link" href="mailto:viktoriia@gomonclinic.com" target="_blank" title="email">viktoriia@gomonclinic.com</a></p>
</div></div></div><div id="a18f2563a881003a9babaf8330d9cf6f" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18ea9503b4800209be8b0a615d58f3d" class="wb_element wb_element_picture" data-plugin="Picture" title=""><div class="wb_picture_wrap"><div class="wb-picture-wrapper"><img loading="lazy" alt="" src="gallery/location-aerial.jpg?ts=1772879214"></div></div></div></div></div><div id="a18f3ac8d03d009d0f1fa794ea69949b" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18ebe0a2840001777311b7dafade030" class="wb_element" data-plugin="CustomHtml" style=" overflow: hidden;"><div style="width: 100%; height: 100%; overflow-y: auto;"><iframe src="https://www.google.com/maps/embed?pb=!1m14!1m8!1m3!1d12133.344080454253!2d32.0695826!3d49.4427166!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x40d14b63c7494e85%3A0x6223723c7c4e505e!2sDr.%20Gomon%20%D0%A1osmetology!5e1!3m2!1suk!2sua!4v1761062626629!5m2!1suk!2sua" width="100%" height="500" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe></div></div></div></div></div></div></div></div></div></div><div id="wb_footer_a188dd94d37a0216abe559d46333c78e" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18ec19bd61d010eb50bf89e3123fe89" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18ec19da3bb004869abb04ca879b3ec" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18f28d4908a00097f08344ea24c1b2c" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18f28f76f7800d7a8613ab727d6296d" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18f28f7a6f80055792116b48a08d220" class="wb_element wb_element_picture" data-plugin="Picture" title="Outside"><div class="wb_picture_wrap"><div class="wb-picture-wrapper"><a href="https://goo.gl/maps/pawu2CSnPNZhySMb7" title="Google Maps" target="_blank"><img loading="lazy" alt="Outside" src="gallery/DSC_0094-EDIT.jpg?ts=1772879214"></a></div></div></div></div></div><div id="a18f28d4908a02eabba2c3e53e1f62d8" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18f28e632a000f046f0771939862680" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><p style="text-align: center;"><span class="wb-stl-custom10">Працюємо <strong><em>БЕЗ</em></strong> вихідних, але <strong><em>ТІЛЬКИ</em></strong> за попереднім <a class="docs-creator" data-_="Link" href="javascript:void(0);" data-popup="wb_popup:Messenger?wbPopupMode=1;w=500;h=500;pagePopup=1;" title="запис"><u>записом</u></a></span></p>
</div><div id="a18f28e6296b0065625945b32403e0de" class="wb_element wb-layout-element wb-layout-has-link" data-plugin="LayoutElement"><a class="wb-layout-link" href="{{base_url}}"></a><div class="wb_content wb-layout-horizontal"><div id="a188dd94be46508454c7063d44a9ea3e" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><h4 class="wb-stl-pagetitle" style="text-align: center;"><strong><span style="color:#00274b;">Dr. Gomon</span></strong></h4>

<p class="wb-stl-normal" style="text-align: center;"><b>Cosmetology</b></p>
</div></div></div></div></div></div></div><div id="a18ec19da3bb02764e64acf965629172" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18edb4464a900b0eda603e4454533f3" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><h3 class="wb-stl-heading3" style="text-align: center;"><a class="docs-creator" data-_="Link" href="contacts">Контакти</a></h3>
</div><div id="a188dd94be465607e006b8fdb52dcff6" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><h3 class="wb-stl-heading3" style="text-align: center;"><u><a class="docs-creator" data-_="Link" href="Публічна-Оферта" title="Публічна оферта"><span style="color:#00274b;">Публічна оферта</span></a></u></h3>
</div><div id="a18ec19e0abd00e8921946a1a84d7a9f" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><h3 class="wb-stl-heading3" style="text-align: center;"><a class="docs-creator" data-_="Link" href="Diplomas-and-Certificates" title="Дипломи й Сертифікати">Дипломи й сертифікати</a></h3>
</div></div></div><div id="a18edc3e2b250091bf8b3618d8172c5e" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18ec244c157001533e4600aafd83b4d" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><p style="text-align: center;"><span class="wb-stl-highlight">GomonClinic © 2019-2026</span></p>
</div></div></div></div></div></div></div><div id="wb_footer_c" class="wb_element" data-plugin="WB_Footer" style="text-align: center; width: 100%;"><div class="wb_footer"></div><script type="text/javascript">
			$(function() {
				var footer = $(".wb_footer");
				var html = (footer.html() + "").replace(/^\s+|\s+$/g, "");
				if (!html) {
					footer.parent().remove();
					footer = $("#footer, #footer .wb_cont_inner");
					footer.css({height: ""});
				}
			});
			</script></div></div></div><script type="text/javascript">$(function() { wb_require(["store/js/StoreCartElement"], function(app) {});})</script>
<div class="wb_pswp" tabindex="-1" role="dialog" aria-hidden="true">
</div>
</div>{{hr_out}}</body>
</html>
