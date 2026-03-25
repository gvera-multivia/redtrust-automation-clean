from multiprocessing import Queue
import time, shutil, tempfile
import uuid
import logging

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# PERSONAL PACKAGES - UTILS
from app.helper.errors.base import ErrorBase
from app.mail.emailDehuFilter import EmailFilter
from app.utils.setup import WebDriverSetup
from app.utils.utils import CERT_SEDES_ACTION, random_wait

class RobotDehu:
    def __init__(self, mail: str, date: str, cliente: str, log_queue: Queue, execution_id: str, module : str ="Altas", portal_link: str = 'https://dehu.redsara.es/es', sede: str = 'dehù',
            n_mails: int = 1,
            multivia: dict = {
                'nif': 'B62798210',
                'purpose': 'MULTIVIA NEGOCIADO Y DEFENSA ADMINISTRATIVA Y JURIDICA ESPAÑA SL',
                'mail': 'notificaciones@xvia-serviciosjuridicos.com',
                'phone': '722761154'
            }):
        self.portal_link = portal_link
        self.sede = sede
        self.multivia = multivia
        self.mail = mail
        self.n_mails = n_mails
        self.cliente = cliente
        self.date = date
        self.module = module
        self.execution_id = execution_id
        self.class_name = f"{self.__class__.__name__}_{uuid.uuid4().hex[:6]}"
        self.log_queue = log_queue
    
    def _log(self, level: int | str, task_id: str, result: str, message: str) -> None:
        self.log_queue.put({
            "level": level,
            "module": self.module,
            "class_name": self.class_name,
            "cliente": self.cliente,
            "task_id": task_id,
            "result": result,
            "message": message
        })
    
    def _login_dehu(self, driver: WebDriverSetup) -> bool:
        end_time = time.time() + 45  # Retry for 30 seconds
        while time.time() < end_time:
            try:
                result = driver.execute_script("""
                    let modal = document.querySelector("body > app-root > app-shared-modal > div > dnt-modal")                                      
                    if (!modal) return {result: false, message: "Modal no encontrado"};
                     
                    let button = modal.querySelector("span > dnt-button").shadowRoot.querySelector("button")                                      
                    if (button) {button.click(); return {result: true, message: "Clicado"};}
                    else return {result: false, message: "Botón no encontrado"};                                  
                """)

                if not result.get('result') and result.get('message') == "Botón no encontrado":
                    self._log(logging.DEBUG, self.sede, 'Pending', f"⚠️ Error al intentar cerrar el modal: {result.get('message')}")
                    random_wait(wait_type='SHORT', wait=True)
                    raise Exception("Botón no encontrado")

                self._check_on_spinner(driver)
                
                WebDriverWait(driver, random_wait('X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/div[1]/div/app-public-view/dnt-hero/div/div/dnt-button'))
                ).click()

                random_wait(wait_type='LONG', wait=True)            
                
                self._check_on_spinner(driver)

                end_click_time = time.time() + 10  # Try for up to 10 seconds
                while time.time() < end_click_time:
                    try:
                        self._check_on_spinner(driver)
                        WebDriverWait(driver, random_wait('X_LONG', wait=False)).until(                                                                                       
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
                        ).click()
                        break  # Exit the loop if the click is successful
                    except Exception as e:
                        random_wait(wait_type='SHORT', wait=True)  # Wait before retrying

                # Definir los elementos a verificar antes de salir
                xpaths = [
                    '/html/body/app-root/app-notifications',
                    '/html/body/app-root/app-comunications',
                    '/html/body/app-root/div[1]/div/app-home-view'                    
                ]
                random_wait(wait_type='X_LONG', wait=True)
                self._check_on_spinner(driver)
                # Check if the XPath exists in the HTML
                for xpath in xpaths:
                    try:
                        if WebDriverWait(driver, random_wait('X_LONG')).until(EC.presence_of_element_located((By.XPATH, xpath))):
                            random_wait(wait_type='MEDIUM', wait=True)
                            return True
                    except Exception as e:
                        self._log(logging.DEBUG, self.sede, 'Pending', f"⚠️ Error checking XPath {xpath}: {e}")
                        continue

                error_paths = [
                    '//*[@id="wrap"]/div/div/span/img',
                    '//*[@id="sub-frame-error"]',
                    '//*[@id="main-frame-error"]'
                    '//*[@id="cuerpo_central_menu"]/p[1]'
                    '/html/body/h1'
                ]

                if self.check_web_error(driver):
                    self._log(logging.ERROR, self.sede, 'Failure', "Web error detected during login navigation.")
                    return False

                error = any(driver.find_elements(By.XPATH, path) for path in error_paths)
                reload = driver.find_elements(By.XPATH, '//*[@id="id-main"]/div/div/div/div/div[2]/div[1]/p[2]/button')

                if error:
                    try:
                        if not 'No se encuentra disponible' in error.text:
                            continue
                        elif not 'Proxy error' in error.text:
                            continue
                        driver.execute_script("window.history.go(-1);")
                        random_wait(wait_type='MEDIUM', wait=True)
                        driver.execute_script("location.reload();")
                        random_wait(wait_type='MEDIUM', wait=True)
                        self._check_on_spinner(driver)
                        WebDriverWait(driver, random_wait('X_LONG')).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
                        ).click()
                        random_wait(wait_type='MEDIUM', wait=True)
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, 'Failure', f"⚠️ Error al recargar la página: {e}")
                        driver.get(self.portal_link)
                    continue
                elif reload:
                    self._log(logging.DEBUG, self.sede, 'Pending', f"Botón de recarga detectado. Intentando hacer clic para reintentar.")
                    try:
                        self._check_on_spinner(driver)
                        WebDriverWait(driver, random_wait('X_LONG')).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
                        ).click()
                        random_wait(wait_type='MEDIUM', wait=True)
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, 'Failure', f"⚠️ Error al hacer clic en el botón de recarga: {e}")
                        driver.get(self.portal_link)

                    continue

            except Exception as e:
                self._log(logging.ERROR, self.sede, 'Failure', str(ErrorBase.ErrorLoginSede(self.sede, e)))
        self._log(logging.ERROR, self.sede, 'Failure', "Login fallido: No se encontraron los elementos esperados.")
        return False
    
    def _check_on_spinner(self, driver) -> None:
        end_time = time.time() + random_wait('LONG', wait=False)  # Check spinner for up to 20 seconds
        while time.time() < end_time:
            try:
                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, '/html/body/app-root/lib-spinner/dnt-spinner//div/slot/div'))
                )
                
            except Exception as e:
                random_wait(wait_type='MEDIUM', wait=True)
                break

    def subscribe(self, id_cliente: str, nif_cif: str) -> bool:
        temp_profile = tempfile.mkdtemp(prefix=f"{self.sede}_temp_profile_")
        driver_setup = WebDriverSetup(
            temp_profile=temp_profile,
            portal_link=self.portal_link,
            module="Altas",
            execution_id=self.execution_id,
            log_dir="logs/altas",
            filename=f"altas",
            cliente=self.cliente,
            task_id=self.sede,
            site=self.sede
        )
        driver = driver_setup.setup_chrome_driver_altas()
        random_wait(wait_type='LONG', wait=True)

        try:
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )

            if not self._login_dehu(driver):
                self._log(logging.INFO, self.sede, "Failure", "Error en login")
                return False, (0, "Error en login")

            def find_contact_mail(mail):
                random_wait(wait_type='LONG', wait=True)
                try:
                    items = driver.execute_script("""
                        let items = document.querySelectorAll(
                            "#pane-0 > app-notices-by-email-section > dnt-section > div > form > div.row.ng-untouched.ng-pristine.ng-valid > div"
                        );

                        for (let i = 0; i < items.length; i++) {
                            let email = items[i]
                                .querySelector("app-email-with-actions > div > div:nth-child(1) > div > app-detail-data-box > div > span.value.dnt-txt-body-300")
                                ?.innerText.trim();

                            if (email === arguments[0]) {
                                return {
                                    result: true,
                                    child: i + 1   // si quieres index 1-based como tu código original
                                };
                            }
                        }

                        return { result: false };
                    """, mail)                       

                    if items.get('result'):
                        return items.get('child')
                    
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error buscando el mail {mail}: {e}")
                return None

            def add_email_field(email):
                # STEP 1: Button to add new contact
                try:
                    # WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    #     EC.element_to_be_clickable((By.XPATH, '//*[@id="pane-0"]/app-notices-by-email-section/dnt-section/div/form/div[2]/dnt-button//button'))
                    # ).click()
                    driver.execute_script("""
                        document.querySelector("#pane-0 > app-notices-by-email-section > dnt-section > div > form > div.dnt-flex.dnt-gap-4.w-100.dnt-justify-end > dnt-button").shadowRoot.querySelector("button").click()
                    """)

                    random_wait(wait_type='SHORT', wait=True)
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error al clicar el botón de añadir mail: {e}")
                    return False, (0, "Error al clicar el botón de añadir mail")
                
                # STEP 2: Fill email field
                try:
                    # OPTION 1: Using Selenium to find and fill the email field
                    # email_sections = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    #     EC.presence_of_all_elements_located((By.XPATH, '//*[@id="pane-0"]/app-notices-by-email-section/dnt-section/div/form/div[1]/div'))
                    # )

                    # for e_section in email_sections:
                    #     email_field = WebDriverWait(e_section, random_wait(wait_type='X_LONG', wait=False)).until(
                    #         EC.presence_of_element_located((By.XPATH, './app-email-with-actions/div/div[1]/div/dnt-input/fieldset/div[2]/div/input'))
                    #     )                                               #//*[@id="pane-0"]/app-notices-by-email-section/dnt-section/div/form/div[1]/div[2]/app-email-with-actions/div/div[1]/div/dnt-input//fieldset/div[2]/div/input
                    #     if email_field.get_attribute('value') == '':
                    #         email_field.clear()
                    #         email_field.send_keys(email)
                    #         return
                    
                    # OPTION 2: Using JavaScript to find and fill the email field
                    email_field = driver.execute_script("""
                        let nodes = document.querySelectorAll("#pane-0 > app-notices-by-email-section > dnt-section > div > form > div.row.ng-pristine > div.col-xs-12.ng-pristine > app-email-with-actions > div > div");
                        let email_sections = [];

                        nodes.forEach((el, index) => {
                            if (index % 3 === 0) {   // 0, 3, 6, 9...
                                email_sections.push(el);
                            }
                        });


                        if (!email_sections || email_sections.length === 0) {
                            return false;
                        } else {
                            for (let section of email_sections) {
                                const host = section.querySelector(" div > dnt-input");
                                if (!host || !host.shadowRoot) {
                                    continue;
                                }
                                const email_field = host.shadowRoot.querySelector("fieldset > div.dnt-input__content > div.dnt-input__wrap > input");
                            
                                if (!email_field) {
                                    continue;
                                }
                            
                                if (email_field.value.trim() === "") {
                                    email_field.value = 'notificaciones@xvia-serviciosjuridicos.com';
                                    email_field.dispatchEvent(new Event("input", { bubbles: true }));
                                    email_field.dispatchEvent(new Event("change", { bubbles: true }));
                                    return true;
                                }
                            }
                        }
                    """, email)

                    return email_field
                
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error añadiendo campo email: {e}")
 
            def insert_verification_code(mail):
                # Paso 1: Clickear botón de verificación si el email existe
                li = find_contact_mail(mail)
                if li:
                    try:
                        driver.execute_script("""
                            document.querySelector(`#pane-0 > app-notices-by-email-section > dnt-section > div > form > div.row > div:nth-child(${arguments[0]}) > app-email-with-actions > div > div:nth-child(3) > div > dnt-button`).shadowRoot.querySelector("button").click()
                        """, li)
                    except Exception:
                        pass

                # Paso 2: Obtener códigos de verificación del email
                email_filter = EmailFilter(
                    username="notificaciones@xvia-serviciosjuridicos.com",
                    password="Noti2017ppp56",
                    imap_server="imap.ionos.es",
                    date=self.date, 
                    log=self._log,
                    imap_port=993
                )
                email_filter.connect()
                
                code = None
                email_filter_params = {
                    "nif": nif_cif,
                    "simple_subject_filter": "Email",
                    "sender_filter": "noreply.dehu@correo.gob.es",
                    "full_subject_filter": 'Verificación de Email',
                    "full_sender_filter": 'noreply.dehu@correo.gob.es'
                }
                
                # Reintentar obtención de códigos hasta 3 veces
                for attempt in range(3):
                    random_wait(wait_type='MEDIUM', wait=True)
                    code = email_filter.extract_verification_code(**email_filter_params)
                    
                    if code:
                        break
                    
                    # Si no hay códigos y quedan intentos, reenviar código
                    if attempt < 2:
                        try:
                            driver.execute_script("""
                                const buttons = document.querySelectorAll("#modalVerify > div.dialog-footer.dnt-flex.dnt-justify-center.dnt-gap-4 > dnt-button");
                                for (let btn of buttons) {
                                    if (btn.textContent.trim().includes("Reenviar código")) {
                                        btn.click();
                                        break;
                                    }
                                }
                            """)
                        except Exception:
                            pass
                        random_wait(wait_type='LONG', wait=True)

                email_filter.disconnect()

                if not code:
                    self._log(logging.ERROR, self.sede, "Failure", "No se pudo obtener código de verificación")
                    return False
                
                # Paso 3: Verificar cada código obtenido
                error_msg_incorrecto = 'El código de verificación introducido es incorrecto o ha expirado.'
                # msg_verificado = 'El código ha sido verificado correctamente.'
                
                try:
                    # Rellenar campo con el código
                    driver.execute_script("""
                        const input = document.querySelector("#modalVerify > div.dnt-flex.dnt-justify-center.dnt-my-6 > dnt-input").shadowRoot.querySelector("fieldset > div.dnt-input__content > div.dnt-input__wrap > input");
                        input.value = arguments[0];
                        input.dispatchEvent(new Event("input", { bubbles: true }));
                        input.dispatchEvent(new Event("change", { bubbles: true }));
                    """, code)
                                        
                    # Clickear botón "Verificar código"
                    driver.execute_script("""
                        const buttons = document.querySelectorAll("#modalVerify > div.dialog-footer.dnt-flex.dnt-justify-center.dnt-gap-4 > dnt-button");
                        for (let btn of buttons) {
                            if (btn.textContent.trim().includes("Verificar código")) {
                                btn.click();
                                break;
                            }
                        }
                    """)
                    
                    random_wait(wait_type='MEDIUM', wait=True)
                    self._check_on_spinner(driver)
                    
                    # Verificar mensaje de error/éxito
                    error_message = None
                    try:
                        error_message = driver.execute_script("""
                            document.querySelector("#modalVerify > div.dnt-flex.dnt-justify-center.dnt-my-6 > dnt-input").shadowRoot.querySelector("fieldset > div.dnt-input__error-message > span").textContent.trim();
                        """)
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error comprobando mensaje: {e}")
                    
                    # Código correcto - retornar éxito
                    # if error_message == msg_verificado:
                    #     return True
                    
                    # Código incorrecto/expirado - reenviar y reintentar
                    if error_message == error_msg_incorrecto:
                        self._log(logging.ERROR, self.sede, "Failure", "El código introducido no es correcto o ha expirado")
                        
                        try:
                            driver.execute_script("""
                                const buttons = document.querySelectorAll("#modalVerify > div.dialog-footer.dnt-flex.dnt-justify-center.dnt-gap-4 > dnt-button");
                                for (let btn of buttons) {
                                    if (btn.textContent.trim().includes("Reenviar código")) {
                                        btn.click();
                                        break;
                                    }
                                }
                            """)
                            random_wait(wait_type='XX_LONG', wait=True)
                            
                            # Obtener código reenviado
                            code_resend = email_filter.extract_verification_code(**email_filter_params)
                            
                            if code_resend:
                                # Reintentar con código reenviado
                                driver.execute_script("""
                                    const input = document.querySelector("#modalVerify > div.dnt-flex.dnt-justify-center.dnt-my-6 > dnt-input").shadowRoot.querySelector("fieldset > div.dnt-input__content > div.dnt-input__wrap > input");
                                    input.value = arguments[0];
                                    input.dispatchEvent(new Event("input", { bubbles: true }));
                                    input.dispatchEvent(new Event("change", { bubbles: true }));
                                """, code_resend)
                                
                                random_wait(wait_type='MEDIUM', wait=True)
                                
                                driver.execute_script("""
                                    const buttons = document.querySelectorAll("#modalVerify > div.dialog-footer.dnt-flex.dnt-justify-center.dnt-gap-4 > dnt-button");
                                    for (let btn of buttons) {
                                        if (btn.textContent.trim().includes("Verificar código")) {
                                            btn.click();
                                            break;
                                        }
                                    }
                                """)
                                
                                random_wait(wait_type='X_LONG', wait=True)
                                self._check_on_spinner(driver)
                                
                                # # Verificar si el código reenviado es válido
                                # final_message = driver.execute_script("""
                                #     document.querySelector("#modalVerify > div.dnt-flex.dnt-justify-center.dnt-my-6 > dnt-input").shadowRoot.querySelector("fieldset > div.dnt-input__error-message > span").textContent.trim();
                                # """)
                                
                                # if final_message == msg_verificado:
                                #     return True
                        except Exception:
                            return False
                                                                
                    return True
                    
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error verificando código: {e}")
                
                return False
            

            include_multivia = False
            # Modal de alta rápida
            try:
                modal = driver.find_elements(By.XPATH, '/html/body/modal-container/div/div/app-modal-redirect/div[2]/button')
            except Exception as e:
                self._log(logging.ERROR, self.sede, "Failure", f"Error buscando el modal de alta rápida: {e}")
                modal = None

            if modal:
                modal[0].click()
                try:
                    random_wait(wait_type='MEDIUM', wait=True)
                    email_field = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="email1"]'))
                    )
                    email_field.clear()
                    email_field.send_keys(self.mail)
                    action = list(CERT_SEDES_ACTION.items())[0]
                    if self.mail != self.multivia.get('mail') and self.n_mails > 1:
                        add_email_field(self.multivia.get('mail'))
                        
                    random_wait(wait_type='MEDIUM', wait=True)
                    WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="acceptSign"]'))
                    ).click()
                    WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="id-main"]/div[2]/form/div[2]/div[2]/div[2]/button'))
                    ).click()
                                        
                    random_wait(wait_type='LONG', wait=True)
                    try: 
                        WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
                        ).click()
                        random_wait(wait_type='LONG', wait=True)
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error en reincio de sesion: {e}")

                    driver.get('https://dehu.redsara.es/contacta')
                    random_wait(wait_type='MEDIUM', wait=True)
                except Exception as e:
                    self._log(logging.INFO, self.sede, "Failure", f"Error introduciendo los mails: {e}")
                    return False, (0, "Error introduciendo los mails")
            else:
                driver.get('https://dehu.redsara.es/es/contact-and-notices')

                random_wait(wait_type='LONG', wait=True)
                li = find_contact_mail(self.mail)
                

                if li:
                    verficacion = driver.execute_script("""
                        try {
                            const selector = `#pane-0 > app-notices-by-email-section > dnt-section > div > form > div.row > div:nth-child(${arguments[0]}) > app-email-with-actions > div > div:nth-child(2) > div > div > dnt-tag`;
                            const element = document.querySelector(selector);
                            console.log(element ? element.textContent.trim() : 'Elemento no encontrado');
                            return element ? element.textContent.trim() : null;
                        } catch(e) {
                            return null;
                        }
                    """, li) 
                    
                    if verficacion == 'Correo electrónico verificado':
                        verificado = True
                    else:
                        verificado = False

                    if verificado:
                        return verificado, list(CERT_SEDES_ACTION.items())[6]
                    else:
                        if self.mail == self.multivia.get('mail'):
                            insert_code = insert_verification_code(self.mail)
                            self._log(logging.INFO, self.sede, "Pending", f"Insertando código de verificación para {self.mail} con resultado {insert_code}")
                            random_wait(wait_type='LONG', wait=True)
                            if not insert_code:
                                return False, (0, "Error verificando el código de verificación")
                            else:
                                li = find_contact_mail(self.multivia.get('mail'))
                                if li:
                                    tag_text = driver.execute_script("""
                                        try {
                                            const element = document.querySelector(`#pane-0 > app-notices-by-email-section > dnt-section > div > form > div.row> div:nth-child(${arguments[0]}) > app-email-with-actions > div > div:nth-child(2) > div > div > dnt-tag`);
                                            return element ? element.textContent.trim() : null;
                                        } catch(e) {
                                            return null;
                                        }
                                    """, li)
                                    verificado = tag_text == 'Correo electrónico verificado'
                                    return verificado, list(CERT_SEDES_ACTION.items())[1]
                        else:
                            self._log(logging.INFO, self.sede, "Pending", f"Mail {self.mail} encontrado pero no verificado, sin acceso al mismo")
                            return False, (0, "Mail encontrado pero sin acceso al mismo")
                else:
                    self._log(logging.INFO, self.sede, "Pending", f"Mail {self.mail} no encontrado, añadiendo a contactos")

                try:
                    try:
                        self._check_on_spinner(driver)
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error esperando al spinner")

                                        
                    try:
                        WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="pane-0"]/app-notices-by-email-section/dnt-section/div/form/div[2]/dnt-button')
                        )).click()
                        # driver.execute_script("""
                        #     document.querySelector("#pane-0 > app-notices-by-email-section > dnt-section > div > form > div.dnt-flex.row > dnt-button").click()
                        # """)

                        random_wait(wait_type='SHORT', wait=True)
                        add_email_field(self.mail)
                        if self.mail != self.multivia.get('mail') and self.n_mails > 1:
                            add_email_field(self.multivia.get('mail'))
                            action = list(CERT_SEDES_ACTION.items())[1]
                            include_multivia = True

                        # WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        #     EC.element_to_be_clickable((By.XPATH, "//*[@id='pane-0']/app-notices-by-email-section/dnt-section/div/form/div[3]/dnt-checkbox//label/span/span[1]/input"))
                        # ).click()

                        driver.execute_script("""
                            document.querySelector("#pane-0 > app-notices-by-email-section > dnt-section > div > form > div.dnt-flex.dnt-py-6.dnt-items-start > dnt-checkbox").shadowRoot.querySelector("label > span > span.dnt-checkbox__input > input").click()
                        """)

                        # WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        #     EC.element_to_be_clickable((By.XPATH, '//*[@id="pane-0"]/app-notices-by-email-section/dnt-section/div/form/div[4]/dnt-button[2]'))
                        # ).click()

                        driver.execute_script("""
                            document.querySelector("#pane-0 > app-notices-by-email-section > dnt-section > div > form > div.dnt-flex.row.dnt-justify-end.dnt-gap-4.dnt-px-2.dnt-flex-col > dnt-button.primary-btn").click()
                        """)

                        random_wait(wait_type='LONG', wait=True)
                        try: 
                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.element_to_be_clickable((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
                            ).click()
                            random_wait(wait_type='LONG', wait=True)
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"Error en reincio de sesion")

                        random_wait(wait_type='LONG', wait=True)
                    
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error rellenando el mail: {e}")
                        return False, (0, "Error rellenando el formulario de añadir contacto")

                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error rellenando el formulario de añadir contact: {e}")
                    return False, (0, "Error rellenando el formulario de añadir contacto")

            # Verificación de email si corresponde
            if self.mail == self.multivia.get('mail'):
                insert_code = insert_verification_code(self.mail)
                if not insert_code:
                    return False, (0, "Error verificando el código de verificación")
                else:
                    li = find_contact_mail(self.multivia.get('mail'))
                    if li:
                        verificado = li.find_element(By.XPATH, './div/div[2]/span[2]/span').text == 'Verificado'
                        return verificado, list(CERT_SEDES_ACTION.items())[0]
            elif self.mail != self.multivia.get('mail') and include_multivia:
                insert_code = insert_verification_code(self.multivia.get('mail'))
                if not insert_code:
                    return False, (0, "Error verificando el código de verificación")
                else:
                    li = find_contact_mail(self.multivia.get('mail'))
                    if li:
                        verficacion = driver.execute_script("""
                            try {
                                const selector = `#pane-0 > app-notices-by-email-section > dnt-section > div > form > div.row > div:nth-child(${arguments[0]}) > app-email-with-actions > div > div:nth-child(2) > div > div > dnt-tag`;
                                const element = document.querySelector(selector);
                                console.log(element ? element.textContent.trim() : 'Elemento no encontrado');
                                return element ? element.textContent.trim() : null;
                            } catch(e) {
                                return null;
                            }
                        """, li) 
                        
                        if verficacion == 'Correo electrónico verificado':
                            verificado = True
                            return verificado, list(CERT_SEDES_ACTION.items())[1]
                        else:
                            verificado = False
                            return verificado, (0, "Error verificando el código de verificación")
                            
            else:
                li = find_contact_mail(self.mail)
                if li:
                    True, (action if action is not None else list(CERT_SEDES_ACTION.items())[6])

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en darse de alta en {self.portal_link}: \n {e}")
            return False, (0, "Error en darse de alta en el portal")
        finally:
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)

