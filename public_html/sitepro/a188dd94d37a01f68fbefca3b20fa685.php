<!DOCTYPE html>
<html lang="uk">
<head>
	<script type="text/javascript">
			</script>
	<meta http-equiv="content-type" content="text/html; charset=utf-8" />
	<title><?php echo htmlspecialchars((isset($seoTitle) && $seoTitle !== "") ? $seoTitle : "About Us"); ?></title>
	<base href="{{base_url}}" />
	<?php echo isset($sitemapUrls) ? (generateCanonicalUrl($sitemapUrls)."\n") : ""; ?>	
	
						<meta name="viewport" content="width=device-width, initial-scale=1" />
					<meta name="description" content="<?php echo htmlspecialchars((isset($seoDescription) && $seoDescription !== "") ? $seoDescription : "Про лікаря Гомон-Павловську Вікторію Вікторівну"); ?>" />
			<meta name="keywords" content="<?php echo htmlspecialchars((isset($seoKeywords) && $seoKeywords !== "") ? $seoKeywords : "косметолог,Черкаси,косметологічний кабінет,студія косметології,пілінг,маска,відбілювання зубів,аугментація,гіалуронова кислота,гіалуронідаза,гіпергідроз,бруксизм,догляд за шкірою обличчя,мезотерапія,ботулінотерапія,біоревіталізація,апаратна косметологія,ін,єкційна косметологія,ультразвукова чистка,скрабер,скраб,корекція обличчя,аугментація скул,аугментація губ,аугментація підборіддня,корекція підборіддя,корекція губ,заповнення носогубних складок,розгладження зморшок,облисіння,ріст волосся,лікування акне,Про нас"); ?>" />
			
	<!-- Facebook Open Graph -->
		<meta property="og:title" content="<?php echo htmlspecialchars((isset($seoTitle) && $seoTitle !== "") ? $seoTitle : "About Us"); ?>" />
			<meta property="og:description" content="<?php echo htmlspecialchars((isset($seoDescription) && $seoDescription !== "") ? $seoDescription : "Про лікаря Гомон-Павловську Вікторію Вікторівну"); ?>" />
			<meta property="og:image" content="<?php echo htmlspecialchars((isset($seoImage) && $seoImage !== "") ? "{{base_url}}".$seoImage : "{{base_url}}gallery_gen/9558c7621adb906341ebf2349ec43222_fit.jpg"); ?>" />
			<meta property="og:type" content="article" />
			<meta property="og:url" content="{{curr_url}}" />
		<!-- Facebook Open Graph end -->

		<meta name="generator" content="Конструктор сайтов" />
			<script src="js/common-bundle.js?ts=20260307122649" type="text/javascript"></script>
	<script src="js/a188dd94d37a01f68fbefca3b20fa685-bundle.js?ts=20260307122649" type="text/javascript"></script>
	<link href="css/common-bundle.css?ts=20260307122649" rel="stylesheet" type="text/css" />
	<link href="css/a188dd94d37a01f68fbefca3b20fa685-bundle.css?ts=20260307122649" rel="stylesheet" type="text/css" id="wb-page-stylesheet" />
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


<body class="site site-lang-uk<?php if (isset($wbPopupMode) && $wbPopupMode) echo ' popup-mode'; ?> " <?php ?>><div id="wb_root" class="root wb-layout-vertical"><div class="wb_sbg"></div><div id="wb_header_a188dd94d37a01f68fbefca3b20fa685" class="wb_element wb-sticky wb-layout-element" data-plugin="LayoutElement" data-h-align="center" data-v-align="top"><div class="wb_content wb-layout-horizontal"><div id="a188dd94be463a75dba900fbd0353b25" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18ead322d680080628d287d243cee71" class="wb_element wb-layout-element wb-layout-has-link" data-plugin="LayoutElement"><a class="wb-layout-link" href="{{base_url}}"></a><div class="wb_content wb-layout-horizontal"><div id="a18ead322d6b001e1977180c2349f733" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><h2 class="wb-stl-custom8" style="text-align: center;"><span style="font-size:22px;"><strong><span style="color:#00274b;">Dr. Gomon</span></strong></span></h2>

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
			'class' => 'wb_this_page_menu_item active',
			'children' => array()
		),
		(object) array(
			'id' => 4,
			'href' => 'contacts',
			'name' => 'Контакти',
			'class' => '',
			'children' => array()
		)
	)
)); ?><div class="clearfix"></div></div></div></div><div id="a188dd94be463f094e15f4bb63aa5685" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a188dd94be46406d239a78d32acc37a2" class="wb_element wb_element_picture wb-anim wb-anim-zoom-in" data-plugin="Picture" title="Instagram"><div class="wb_picture_wrap" style="height: 100%"><div class="wb-picture-wrapper" style="overflow: visible; display: flex"><a href="https://m.instagram.com/dr.gomon" title="Instagram" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="30" viewBox="0 0 1793.982 1793.982" style="direction: ltr; color:#00274b"><text x="129.501415" y="1537.02" font-size="1792" fill="currentColor" style='font-family: "FontAwesome"'></text></svg></a></div></div></div><div id="a188dd94be4641bdb8744d1c11db0d1f" class="wb_element wb_element_picture wb-anim wb-anim-zoom-in" data-plugin="Picture" title="Facebook"><div class="wb_picture_wrap" style="height: 100%"><div class="wb-picture-wrapper" style="overflow: visible; display: flex"><a href="https://m.facebook.com/dr.gomon" title="Facebook" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="30" viewBox="0 0 1793.982 1793.982" style="direction: ltr; color:#00274b"><text x="385.501415" y="1537.02" font-size="1792" fill="currentColor" style='font-family: "FontAwesome"'></text></svg></a></div></div></div><div id="a188dd94be464213c9058d2ac34834c4" class="wb_element wb_element_picture wb-anim wb-anim-zoom-in" data-plugin="Picture" title="Google Maps"><div class="wb_picture_wrap" style="height: 100%"><div class="wb-picture-wrapper" style="overflow: visible; display: flex"><a href="https://goo.gl/maps/pawu2CSnPNZhySMb7" title="Google Maps" target="_blank"><svg xmlns="http://www.w3.org/2000/svg" width="30" viewBox="0 0 1793.982 1793.982" style="direction: ltr; color:#00274b"><text x="129.501415" y="1537.02" font-size="1792" fill="currentColor" style='font-family: "FontAwesome"'></text></svg></a></div></div></div></div></div></div></div></div></div><div id="wb_main_a188dd94d37a01f68fbefca3b20fa685" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a188dd94be4602a8e754f4fda8e8d231" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18ead8a97e00088bf2957c4caa7da17" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><p class="wb-stl-normal"><strong>Лікар косметолог-ін'єкціоніст</strong></p>

<p class="wb-stl-normal"><em><b>Гомон-Павловська Вікторія Вікторівна</b></em></p>
</div><div id="a188dd94be4603a0bda550e989289629" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18eaa7aa21c0026541fac3ad1a99496" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18ead7ef4b400107e238f8d0adc1c92" class="wb_element wb-prevent-layout-click wb_gallery" data-plugin="Gallery"><script type="text/javascript">
			$(function() {
				(function(GalleryLib) {
					var el = document.getElementById("a18ead7ef4b400107e238f8d0adc1c92");
					var lib = new GalleryLib({"id":"a18ead7ef4b400107e238f8d0adc1c92","height":"auto","type":"slideshow","trackResize":true,"interval":0,"speed":100,"images":[{"thumb":"gallery_gen\/5f57efa3bc4fe444a8710d6be9c26869_996x1351.9301972686_fill.jpg","src":"gallery_gen\/9558c7621adb906341ebf2349ec43222_fit.jpg?ts=1772879214","width":2636,"height":3578,"title":"","link":{"url":"https:\/\/www.instagram.com\/p\/CwfX2_WIPYm\/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==","target":false},"description":"","address":{}},{"thumb":"gallery_gen\/d172a3a9629ff0331163ad2ce0f4970e_1036x1295_fill.jpeg","src":"gallery_gen\/11edee01a0d5f7ebe74c832f36a822a3_fit.jpeg?ts=1772879214","width":1440,"height":1800,"title":"","link":null,"description":"","address":{}},{"thumb":"gallery_gen\/ac39836c4216f22c67ca4d5df1187371_fill.jpeg","src":"gallery_gen\/f921fed453046d3040554ac10dc81e20_fit.jpeg?ts=1772879214","width":1029,"height":1104,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/5ffe4e3bd21345e4a9043626208dfaa7_1020x1316.1168639053_fill.jpg","src":"gallery_gen\/3804359685358cc8bbef1af2c4c5f183_fit.jpg?ts=1772879214","width":2704,"height":3489,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/d2eaca484fab3d507c30a1dfb055a87e_1397.441003528x964_fill.jpg","src":"gallery_gen\/694279552357630670819bcae667d6e4_fit.jpg?ts=1772879214","width":3698,"height":2551,"title":"","link":null,"description":"","address":""}],"border":{"border":"5px none #00008c"},"padding":0,"thumbWidth":290,"thumbHeight":290,"thumbAlign":"center","thumbPadding":6,"thumbAnim":"","thumbShadow":"","imageCover":true,"disablePopup":true,"controlsArrow":"shevron-circle","controlsArrowSize":14,"controlsArrowStyle":{"normal":{"color":"rgba(190, 141, 137, 0.7)","shadow":{"angle":135,"distance":0,"size":0,"blur":1,"color":"#000000","forText":true,"css":{"text-shadow":"0px 0px 1px #000000"}}},"hover":{"color":"rgba(168, 200, 230, 0.7)","shadow":{"angle":135,"distance":0,"size":0,"blur":1,"color":"#222222","forText":true,"css":{"text-shadow":"0px 0px 1px #222222"}},"border":{"differ":false,"differRadius":false,"color":["#000000","#000000","#000000","#000000"],"style":["none","none","none","none"],"weight":0,"radius":null,"css":{"border":"0px none #000000"},"cssRaw":"border: 0px none #000000;"}},"active":{"color":"#FFFFFF","shadow":{"angle":135,"distance":0,"size":0,"blur":1,"color":"#000000","forText":true,"css":{"text-shadow":"0px 0px 1px #000000"}}}},"slideOpacity":100,"showPictureCaption":"always","captionIncludeDescription":false,"captionPosition":"center bottom","mapTypeId":"roadmap","markerIconTypeId":"thumbs","zoom":2,"mapCenter":{"latLng":{"lat":42.553080288956,"lng":-2.8125},"text":"42.553080288955805, -2.8125"},"key":"AIzaSyAcNYVaN_XQAj--scwH8X71jj0waa442BY","theme":"default","color":"#eeeeee","showSatellite":true,"showZoom":true,"showStreetView":true,"showFullscreen":true,"allowDragging":true,"showRoads":true,"showLandmarks":true,"showLabels":true,"locale":"uk_UA","pauseOnHover":false});
					lib.appendTo(el);
				})(window.wbmodGalleryLib);
			});
		</script></div></div></div><div id="a188dd94be46056b6cc74b3c9c3b89cf" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a188dd94be4609a2c422dc265859973d" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><p class="wb-stl-footer"> </p>

<p class="wb-stl-footer">    Мене звати Вікторія Гомон-Павловська, за освітою я лікар-стоматолог, навчалася в НМУ ім. О. О. Богомольця на бюджетній основі та була президентським стипендіантом Малої Академії Наук («Біологія людини»).<br>
Мабуть, з того періоду в мене і виникла така сильна любов до біології, фізіології, анатомії людини.<br><br>
    Щодо моєї професії, то я саме той лікар, який 7 років вивчав анатомію, патологію, диф. діагностику захворювань і лікування голови та шиї!<br>
(Так, стоматолог- це не лише зуб. Щоб Ви краще розуміли особливості даної професії, то лише лікарі-стоматологи можуть стати щелепно-лицевими хірургами через особливість навчальної програми в мед.закладах)<br><br>
Отже, буде не дивним, якщо я скажу, що інʼєкції - це моя пристрасть і любов.</p>

<ul><li class="wb-stl-footer">Обожнюю визначати різні мʼязові морфотипи в пацієнтів</li>
<li class="wb-stl-footer">Бачу, як працює мімічна, жувальна мускулатура, патологію зубо-щелепної системи в кожного пацієнта і ОБОВʼЯЗКОВО скажу про це</li>
<li class="wb-stl-footer">Озвучу всі можливі методи лікування, профілактики та вирішення Вашої естетичної проблеми</li>
<li class="wb-stl-footer">Я за профілактику старіння шкіри і звʼязкового апарату. Тому якщо Ви налаштовані на довготривале підтримання краси та здоровʼя, а не короткотривалий миттєвий результат, в нас з Вами буде метч </li>
<li class="wb-stl-footer">Часто відмовляю від непотрібних процедур та інʼєкцій. Не ображайтесь, будь ласка, якщо ви прийдете за інʼєкціями філлера, а вийдете з інʼєкціями ботулотоксину. Кінцевий результат Вас порадує, довіртесь!</li>
</ul><p class="wb-stl-footer"> </p>

<p class="wb-stl-footer">    Ще одна моя пристрасть - це підбір ДІЄВОГО домашнього догляду. Я за активні компоненти! Тому підберу Вам 100% дієвий засіб замість 20 не потрібних баночок.</p>

<p class="wb-stl-footer"> </p>

<p class="wb-stl-footer">    І ще декілька слів про мій шлях в косметологію. З кінця 2016 року (5 курс університету) я почала працювати спеціалістом з лазерної епіляції (ЛЕ).</p>

<p class="wb-stl-footer">Працювала з 2016 до 2019 в топових студіях Києва (Lazergrad, LazerVita, Zlatko, Orchid Beauty) і паралельно лікарем-стоматологом (інтерном) в державній поліклініці. В 2019 році пройшла перші курси з інʼєкційної косметології і в 2020 отримала диплом косметолога-естетиста в Космотрейді.</p>

<p class="wb-stl-footer">З того часу намагаюсь щомісяця відвідувати хоча б 1 навчання з косметології (семінар, вебінар, майстер-клас, конгрес). Адже бути медиком - це бути вічним студентом. Як то кажуть: «Не має меж для досконалості»</p>
</div></div></div></div></div><div id="a188dd94be4651339192e4bc04873f42" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a188dd94be4653bf25e0886de2bf46e0" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><p class="wb-stl-normal"><strong>Що про нас кажуть клієнти:</strong></p>
</div><div id="a18eaffbc4cc003a945d9165d5998685" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18eaffddefc00a8341d53535ef08f96" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18eaffdd18700d166db9cee0cb1b908" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><p class="wb-stl-normal"><u><strong>В <a class="docs-creator" data-_="Link" href="https://www.m.instagram.com/stories/highlights/17843590348404945/" rel="nofollow" target="_blank">Instagram</a></strong></u></p>
</div><div id="a18ee31f0ab0003a645a72607fd7ffcd" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18eaff308fb00375afcd59cd5a92d1b" class="wb_element wb-prevent-layout-click wb_gallery" data-plugin="Gallery"><script type="text/javascript">
			$(function() {
				(function(GalleryLib) {
					var el = document.getElementById("a18eaff308fb00375afcd59cd5a92d1b");
					var lib = new GalleryLib({"id":"a18eaff308fb00375afcd59cd5a92d1b","height":"auto","type":"slideshow","trackResize":true,"interval":0,"speed":250,"images":[{"thumb":"gallery_gen\/bf60e687f1967245361c71b2460ed4cb_fill.jpeg","src":"gallery_gen\/89365233340fa3a19205d3b0722f7c8b_fit.jpeg?ts=1772879214","width":640,"height":1138,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/cb50c0c138f7d807f1c0dbe364584a31_fill.jpeg","src":"gallery_gen\/6f95a7b851eb61a2ccb16cbd78fb5340_fit.jpeg?ts=1772879214","width":640,"height":1138,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/4aa6c4e8f578ec902c5294e8b556f4d7_fill.jpeg","src":"gallery_gen\/792ee461f68ebda4e181d7b97e93e1c8_fit.jpeg?ts=1772879214","width":640,"height":1138,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/65e018adfc20db16d102761e75173fd5_fill.jpeg","src":"gallery_gen\/8ddd95956ba5b1cb4e4dce85c59dbe03_fit.jpeg?ts=1772879214","width":640,"height":640,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/ebb09744094e4bb34a46a38a221048b5_fill.jpeg","src":"gallery_gen\/a107e1079b52f4371632db48b35bf875_fit.jpeg?ts=1772879214","width":640,"height":640,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/fca88863cf8653b15c4fc7a81229d4d5_fill.jpeg","src":"gallery_gen\/ff2f4646aa30733934b41200c4669c5c_fit.jpeg?ts=1772879214","width":640,"height":640,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/033e2f8518c09bd0b0e28117568d947d_fill.jpeg","src":"gallery_gen\/6d9c4db8d04eec0d88da0d7876e1916b_fit.jpeg?ts=1772879214","width":640,"height":640,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/fc34eea8b46ac91fc620d77ec12f9b73_fill.jpeg","src":"gallery_gen\/2662c07cbbfc07091e2c96578de0700c_fit.jpeg?ts=1772879214","width":640,"height":640,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/ccb518a80113e63173b5c37c8ef5764c_fill.jpeg","src":"gallery_gen\/8fa9f4b0c408c4fa662511e1efe0ca60_fit.jpeg?ts=1772879214","width":397,"height":397,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/755186b771cc6da2dcfa579f4beefa1b_fill.jpeg","src":"gallery_gen\/c1d211dc326b5dfe248c1ea792f6b985_fit.jpeg?ts=1772879214","width":319,"height":319,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/5d8bd076269449683dbffbbc1f7bbf2f_fill.jpeg","src":"gallery_gen\/d7d01a49ccab06d6af08fdd35b2f882d_fit.jpeg?ts=1772879214","width":640,"height":640,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/0a7da701d98e0d86df36dec67d1bc67d_fill.jpeg","src":"gallery_gen\/bf3837efe7eade07962f2a37a7ec768a_fit.jpeg?ts=1772879214","width":640,"height":640,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/b60e2536c66f33f205c274791dda0ccb_fill.jpeg","src":"gallery_gen\/d6bd66b571350a02fcf1eed2254cba60_fit.jpeg?ts=1772879214","width":640,"height":640,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/3447fad6dfc7b663b30e815543b3a2f5_fill.jpeg","src":"gallery_gen\/94f18f01a686ca85bcb3b39968774b72_fit.jpeg?ts=1772879214","width":640,"height":640,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/6e9807ac5298bce81c3a052f56ce130d_fill.jpeg","src":"gallery_gen\/33a7ea389245a90a635a63a87758459c_fit.jpeg?ts=1772879214","width":640,"height":640,"title":"","link":null,"description":"","address":""},{"thumb":"gallery_gen\/929238f8d6be909faae5a9ca954cc16f_fill.jpeg","src":"gallery_gen\/7d9a54999ad4cd296a7a033346787eaf_fit.jpeg?ts=1772879214","width":640,"height":640,"title":"","link":null,"description":"","address":""}],"border":{"border":"5px none #00008c"},"padding":0,"thumbWidth":290,"thumbHeight":290,"thumbAlign":"center","thumbPadding":6,"thumbAnim":"","thumbShadow":"","imageCover":true,"disablePopup":false,"controlsArrow":"shevron-circle","controlsArrowSize":14,"controlsArrowStyle":{"normal":{"color":"rgba(212, 165, 165, 0.7)","shadow":null},"hover":{"color":"rgba(168, 200, 230, 0.7)","shadow":{"angle":135,"distance":0,"size":0,"blur":1,"color":"#222222","forText":true,"css":{"text-shadow":"0px 0px 1px #222222"}},"border":{"differ":false,"differRadius":false,"color":["#000000","#000000","#000000","#000000"],"style":["none","none","none","none"],"weight":0,"radius":null,"css":{"border":"0px none #000000"},"cssRaw":"border: 0px none #000000;"}},"active":{"color":"#FFFFFF","shadow":{"angle":135,"distance":0,"size":0,"blur":1,"color":"#000000","forText":true,"css":{"text-shadow":"0px 0px 1px #000000"}}}},"slideOpacity":100,"showPictureCaption":"none","captionIncludeDescription":false,"captionPosition":"center bottom","mapTypeId":"roadmap","markerIconTypeId":"thumbs","zoom":2,"mapCenter":{"latLng":{"lat":42.553080288956,"lng":-2.8125},"text":"42.553080288955805, -2.8125"},"key":"AIzaSyAcNYVaN_XQAj--scwH8X71jj0waa442BY","theme":"default","color":"#eeeeee","showSatellite":true,"showZoom":true,"showStreetView":true,"showFullscreen":true,"allowDragging":true,"showRoads":true,"showLandmarks":true,"showLabels":true,"locale":"uk_UA","pauseOnHover":false});
					lib.appendTo(el);
				})(window.wbmodGalleryLib);
			});
		</script></div></div></div></div></div><div id="a18eaffd3d0300fd6416fc731226142e" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18eaffd4850008adfdf4661ca4e3ca0" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><p class="wb-stl-normal"><span style="color:#00274b;"><u><strong>В <a class="docs-creator" data-_="Link" href="https://goo.gl/maps/pawu2CSnPNZhySMb7" rel="nofollow" target="_blank">Google</a></strong></u></span></p>
</div><div id="a18eaffb2f2e000ac03e331462ef1033" class="wb_element" data-plugin="CustomHtml"><div style="width: 100%; height: 100%;"><iframe src="https://cd23915c80ed4e4a9a0d95db9d9ff230.elf.site" width="100%" height="1000" frameborder="0"></iframe></div></div></div></div></div></div></div></div></div></div><div id="a18ee23cd36d007f9c3638c2a2db0ba6" class="wb_element" data-plugin="CustomHtml"><div style="width: 100%; height: 100%;"><script src="https://static.elfsight.com/platform/platform.js" data-use-service-core defer></script><div class="elfsight-app-42951e69-a477-439c-b5bd-0e1914aacea0" data-elfsight-app-lazy></div></div></div></div></div><div id="wb_footer_a188dd94d37a01f68fbefca3b20fa685" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18ec19bd61d010eb50bf89e3123fe89" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18ec19da3bb004869abb04ca879b3ec" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18f28d4908a00097f08344ea24c1b2c" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18f28f76f7800d7a8613ab727d6296d" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-horizontal"><div id="a18f28f7a6f80055792116b48a08d220" class="wb_element wb_element_picture" data-plugin="Picture" title="Outside"><div class="wb_picture_wrap"><div class="wb-picture-wrapper"><a href="https://goo.gl/maps/pawu2CSnPNZhySMb7" title="Google Maps" target="_blank"><img loading="lazy" alt="Outside" src="gallery/DSC_0094-EDIT.jpg?ts=1772879214"></a></div></div></div></div></div><div id="a18f28d4908a02eabba2c3e53e1f62d8" class="wb_element wb-layout-element" data-plugin="LayoutElement"><div class="wb_content wb-layout-vertical"><div id="a18f28e632a000f046f0771939862680" class="wb_element wb_text_element" data-plugin="TextArea" style=" line-height: normal;"><p style="text-align: center;"><span class="wb-stl-custom10">Працюємо <strong><em>БЕЗ</em></strong> вихідних, але <strong><em>ТІЛЬКИ</em></strong> за попереднім <a class="docs-creator" data-_="Link" href="javascript:void(0);" data-popup="wb_popup:Messenger?wbPopupMode=1;w=500;h=500;pagePopup=1;" title="запис"><u>записом</u></a></span></p>
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
